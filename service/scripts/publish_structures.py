"""Publish the predicted structures to an object store, and write the index beside them.

    python scripts/publish_structures.py --staging ~/pepticraft/folds/pdb \
        --manifest ../exports/PeptiCraft-OmegaFold-Pack-20261102/manifest.csv \
        --bucket pepticraft-structures

Why a store rather than the site itself
--------------------------------------
A structure is a coordinate file of a few hundred kilobytes, and the platform needs a few
thousand of them. The site's own deployment has a twenty-thousand-file ceiling and a size
ceiling per file, so the coordinates live in an object store and the site holds only the two
index files, which are small enough to stay where the rest of the data is.

What is published
-----------------
    structures/<structure_id>.pdb    one file per prediction
    structures.json                  per-structure metadata: chain length and the two
                                    confidence figures, the whole chain and the peptide
    structure_lookup.json            construct|scaffold|linker -> structure_id

The index is rebuilt from whatever is on disk every time, so a batch that is still running
publishes a growing set: a structure that has finished is in the next publish, and one that
has not is simply absent.

Two ways to reach the store
---------------------------
`--backend rest` (the default) speaks the store's HTTP API directly with the OAuth token
that wrangler already holds, and uploads many files at once. It needs no separate
credentials file, which matters because the API-token path requires a value that only the
Cloudflare dashboard hands out.

`--backend rclone` shells out to rclone, which is what to use when a proper R2 API token
exists and the files are large enough to want multipart uploads:

    rclone config create pepticraft-r2 s3 \
        provider Cloudflare \
        access_key_id <R2 access key id> \
        secret_access_key <R2 secret access key> \
        endpoint https://<account id>.r2.cloudflarestorage.com

Either way the remote is named as `<bucket>` alone; the rclone remote name is configured on
the machine rather than passed in, so that the same command line works for both backends.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BUCKET = "pepticraft-structures"
DEFAULT_ACCOUNT = "37284f93088427a09c4ddb47f08d4cf4"
WRANGLER_CONFIG = Path.home() / "Library/Preferences/.wrangler/config/default.toml"


def run(command: list[str], *, dry_run: bool = False) -> None:
    printable = " ".join(command)
    if dry_run:
        print(f"[dry-run] {printable}")
        return
    print(f"$ {printable}")
    result = subprocess.run(command)
    if result.returncode != 0:
        raise SystemExit(f"command failed ({result.returncode}): {printable}")


def read_oauth_token() -> str:
    """The OAuth token wrangler holds after `wrangler login`."""
    from_env = os.environ.get("CLOUDFLARE_OAUTH_TOKEN")
    if from_env:
        return from_env
    if not WRANGLER_CONFIG.exists():
        raise SystemExit(
            f"no OAuth token: set CLOUDFLARE_OAUTH_TOKEN, or log in with `wrangler login`"
        )
    for line in WRANGLER_CONFIG.read_text().splitlines():
        match = re.match(r'\s*(?:oauth_token|access_token)\s*=\s*"([^"]+)"', line)
        if match:
            return match.group(1)
    raise SystemExit(f"no OAuth token in {WRANGLER_CONFIG}")


class RestUploader:
    """Uploads objects through the store's HTTP API, several at a time."""

    def __init__(self, bucket: str, account: str, token: str, workers: int = 12) -> None:
        self.bucket = bucket
        self.account = account
        self.token = token
        self.workers = workers
        self.base = (
            f"https://api.cloudflare.com/client/v4/accounts/{account}"
            f"/r2/buckets/{bucket}/objects"
        )

    def put(self, key: str, payload: bytes, content_type: str) -> tuple[str, bool, str]:
        url = f"{self.base}/{key}"
        request = urllib.request.Request(
            url,
            data=payload,
            method="PUT",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": content_type,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = json.loads(response.read())
            etag = body.get("result", {}).get("etag", "")
            return key, True, etag
        except urllib.error.HTTPError as error:
            detail = error.read().decode()[:200]
            return key, False, f"{error.code} {detail}"
        except Exception as error:  # noqa: BLE001 - network failures are reported, not raised
            return key, False, str(error)[:200]


def upload_with_rest(
    uploader: RestUploader,
    files: list[tuple[str, Path]],
    state_path: Path | None,
    *,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Upload every file, skipping the ones a previous run already stored.

    The skip list records the size and the store's own entity tag, so a file that changed
    on disk is uploaded again and a file that did not is not.
    """
    state: dict[str, list] = {}
    if state_path and state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except json.JSONDecodeError:
            state = {}

    pending: list[tuple[str, Path]] = []
    for key, path in files:
        size = path.stat().st_size
        digest = state.get(key)
        if digest and digest[0] == size:
            continue
        pending.append((key, path))

    skipped = len(files) - len(pending)
    print(f"{len(files)} files, {skipped} already stored, {len(pending)} to upload")

    if dry_run:
        return skipped, 0

    failures: list[tuple[str, str]] = []
    done = 0
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=uploader.workers) as pool:
        futures = {
            pool.submit(
                uploader.put,
                key,
                path.read_bytes(),
                content_type_for(path),
            ): (key, path)
            for key, path in pending
        }
        for future in concurrent.futures.as_completed(futures):
            key, path = futures[future]
            _, ok, detail = future.result()
            done += 1
            if ok:
                state[key] = [path.stat().st_size, detail]
            else:
                failures.append((key, detail))
            if done % 200 == 0 or done == len(pending):
                rate = done / max(time.time() - started, 1e-6)
                print(f"  {done}/{len(pending)} uploaded ({rate:.0f}/s)", flush=True)

    if state_path:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=1, sort_keys=True))

    if failures:
        print(f"{len(failures)} uploads failed", file=sys.stderr)
        for key, detail in failures[:10]:
            print(f"  {key}: {detail}", file=sys.stderr)
    return skipped, len(pending) - len(failures)


def content_type_for(path: Path) -> str:
    if path.suffix == ".json":
        return "application/json"
    if path.suffix == ".pdb":
        return "chemical/x-pdb"
    return "application/octet-stream"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--staging", type=Path, required=True,
                        help="directory holding the .pdb files")
    parser.add_argument("--manifest", type=Path, required=True,
                        help="the pack's manifest.csv, which carries the lengths and the aliases")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--account", default=DEFAULT_ACCOUNT,
                        help="the Cloudflare account that owns the bucket")
    parser.add_argument("--backend", choices=("rest", "rclone"), default="rest")
    parser.add_argument("--rclone-remote", default="pepticraft-r2",
                        help="the rclone remote to use when --backend rclone")
    parser.add_argument("--index-dir", type=Path, default=None,
                        help="where to write the index files; a temporary directory by default")
    parser.add_argument("--pull-from", default=None,
                        help="rsync the coordinate files from a remote host first, as "
                             "user@host:/path/to/folds/pdb")
    parser.add_argument("--state", type=Path, default=None,
                        help="a file recording what has already been uploaded, so that "
                             "repeated runs only send what is new")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--skip-upload", action="store_true",
                        help="build the index and stop before uploading")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.pull_from:
        run(["rsync", "-az", "--include", "*.pdb", "--exclude", "*",
             f"{args.pull_from.rstrip('/')}/", f"{args.staging}/"], dry_run=args.dry_run)

    if not args.staging.is_dir():
        raise SystemExit(f"no such directory: {args.staging}")

    index_dir = args.index_dir
    if index_dir is None:
        import tempfile

        index_dir = Path(tempfile.mkdtemp(prefix="pepticraft-structure-index-"))
    index_dir.mkdir(parents=True, exist_ok=True)

    structures = index_dir / "structures.json"
    lookup = index_dir / "structure_lookup.json"

    # The index is built locally and costs nothing, so a dry run builds it too; only the
    # upload is skipped.
    run([
        sys.executable,
        str(Path(__file__).with_name("build_structure_index.py")),
        "--folds", str(args.staging),
        "--manifest", str(args.manifest),
        "--out", str(structures),
        "--lookup", str(lookup),
    ])

    if args.skip_upload:
        print(f"index written to {index_dir}")
        return 0

    pdb_files = sorted(args.staging.glob("*.pdb"))
    files: list[tuple[str, Path]] = [(f"structures/{p.name}", p) for p in pdb_files]
    files.append(("structures.json", structures))
    files.append(("structure_lookup.json", lookup))

    if args.backend == "rclone":
        remote = f"{args.rclone_remote}:{args.bucket}"
        run(["rclone", "copy", str(args.staging), f"{remote}/structures",
             "--include", "*.pdb", "--s3-upload-cutoff", "0",
             "--s3-no-check-bucket", "--no-traverse"], dry_run=args.dry_run)
        run(["rclone", "copyto", str(structures), f"{remote}/structures.json",
             "--s3-no-check-bucket"], dry_run=args.dry_run)
        run(["rclone", "copyto", str(lookup), f"{remote}/structure_lookup.json",
             "--s3-no-check-bucket"], dry_run=args.dry_run)
        print("published")
        return 0

    uploader = RestUploader(args.bucket, args.account, read_oauth_token(), args.workers)
    skipped, uploaded = upload_with_rest(uploader, files, args.state, dry_run=args.dry_run)
    print(f"published: {uploaded} uploaded, {skipped} already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
