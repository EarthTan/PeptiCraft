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

The rate limit, and why this uploader obeys it
---------------------------------------------
Cloudflare's own documentation states that the REST API is limited to 1,200 requests per
five minutes across all R2 operations on an account, and that the S3-compatible API or a
Workers binding is the way to do high-throughput object operations. The OAuth token this
backend uses is an API token, so it spends that administrative quota rather than the
object-quota path.

That limit is not a formality at this scale. A run produces twenty-six thousand files, and
uploading them as fast as the network allows spends the whole five-minute quota in seconds
and then answers every remaining request with 429. The symptom is deceptive: the first
thousand files succeed, the rest fail, and the next run — which begins with a fresh quota —
fails in exactly the same place, so the count in the store never grows.

So the uploader paces itself. It keeps a running count of requests inside the current
five-minute window and waits rather than issuing a request that would be refused, and a
request that is refused anyway is retried after the window rolls over. The result is a
publish that takes hours instead of one that takes minutes and achieves nothing.

Two further rules follow from the same quota. The index files are uploaded last and only
once every coordinate file they refer to is present, because an index that names a file the
store does not have produces a broken page rather than a missing one. And a file whose
upload failed is not recorded as uploaded, so the next pass retries it.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_BUCKET = "pepticraft-structures"
DEFAULT_ACCOUNT = "37284f93088427a09c4ddb47f08d4cf4"
WRANGLER_CONFIG = Path.home() / "Library/Preferences/.wrangler/config/default.toml"

# The API's published limit: 1,200 requests per five minutes, across all R2 operations on
# the account. The uploader spends most of that budget on coordinate files, so it aims below
# the ceiling rather than at it.
RATE_LIMIT = 1200
RATE_WINDOW = 300.0
# The fraction of the ceiling the uploader aims for, leaving room for the requests other
# tools on the account make.
RATE_TARGET = 0.7


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
    """The OAuth token wrangler holds after `wrangler login`.

    The token is short-lived: wrangler's OAuth grant expires within hours, and a batch that
    runs for months will outlive it many times over. So the token is refreshed when it is
    about to expire, and refreshed again if a request is refused because it expired
    meanwhile. `CLOUDFLARE_OAUTH_TOKEN` in the environment overrides the file, which is the
    way to run this on a machine whose token is managed elsewhere.
    """
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


def token_expiry() -> datetime | None:
    """When the stored token stops being accepted, if the file says."""
    if not WRANGLER_CONFIG.exists():
        return None
    match = re.search(r'expiration_time\s*=\s*"([^"]+)"', WRANGLER_CONFIG.read_text())
    if not match:
        return None
    try:
        return datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
    except ValueError:
        return None


def wrangler_commands() -> list[list[str]]:
    """Ways to run wrangler on this machine, most direct first.

    A launch agent does not inherit the session's PATH, so the bare names "npx" and
    "node" are not found even though both are installed. The cached copy of wrangler that
    npx keeps is preferred, because calling it directly needs no registry access and
    cannot fail on a network hiccup; the npx wrapper is the fallback.
    """
    commands: list[list[str]] = []

    node_dirs = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        str(Path.home() / ".workbuddy/binaries/node/versions"),
    ]
    versions = Path.home() / ".workbuddy/binaries/node/versions"
    if versions.is_dir():
        node_dirs.extend(str(p / "bin") for p in sorted(versions.iterdir(), reverse=True))

    cache = Path.home() / ".npm/_npx"
    if cache.is_dir():
        for candidate in sorted(cache.glob("*/node_modules/.bin/wrangler"), reverse=True):
            if os.access(candidate, os.X_OK):
                commands.append([str(candidate)])
                break

    for node_dir in node_dirs:
        npx = Path(node_dir) / "npx"
        if npx.is_file() and os.access(npx, os.X_OK):
            commands.append([str(npx), "wrangler"])
            break

    return commands


def refresh_token() -> str | None:
    """Renew the stored OAuth token. Returns the new token, or None.

    Wrangler owns this exchange, and it holds a refresh token alongside the access token,
    so the renewal is silent: any wrangler command that needs an authenticated call will
    perform the exchange itself and write the new token back to its configuration file.
    `wrangler whoami` is the cheapest command that forces it, and it reports whether the
    renewal worked without touching any of the account's resources.

    Nothing here opens a browser. `wrangler login` would, and it is the one thing this
    function must not do: the caller runs unattended on a timer, so a login means a window
    appearing on somebody's desktop every half hour, forever, and nobody there to finish it.
    When the refresh token is gone the honest outcome is to stop and say so; a login is a
    person's decision, made by hand, in a terminal.
    """
    commands = wrangler_commands()
    if not commands:
        print(
            "no wrangler on this machine, so the Cloudflare token cannot be renewed; set "
            "CLOUDFLARE_OAUTH_TOKEN in the environment instead",
            file=sys.stderr,
        )
        return None

    env = dict(os.environ)
    node_paths = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        str(Path.home() / ".workbuddy/binaries/node/versions"),
    ]
    versions = Path.home() / ".workbuddy/binaries/node/versions"
    if versions.is_dir():
        node_paths.extend(str(p / "bin") for p in sorted(versions.iterdir(), reverse=True))
    env["PATH"] = ":".join(node_paths + [env.get("PATH", "")])

    before = read_oauth_token() if WRANGLER_CONFIG.exists() else ""
    for base in commands:
        command = base + ["whoami"]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
                cwd=str(Path.home()),
            )
        except OSError as exc:
            print(f"could not run {' '.join(command)}: {exc}", file=sys.stderr)
            continue
        if result.returncode != 0:
            # This form could not reach the service at all; the next one might, and asking
            # twice costs one request rather than a browser window.
            continue
        try:
            token = read_oauth_token()
        except SystemExit:
            return None
        if token != before:
            print("renewed the Cloudflare OAuth token", file=sys.stderr)
            return token
        # Wrangler answered, so the exchange was attempted and left the token alone. Trying
        # the other forms would ask the same service the same question and get the same
        # answer; there is nothing further this machine can do without a person.
        break
    print(
        "wrangler could not renew the Cloudflare OAuth token; uploads are stopped until "
        "`wrangler login` is run in a terminal by hand",
        file=sys.stderr,
    )
    return None


class RateLimiter:
    """Keeps the request count inside the API's five-minute window.

    The window slides: a request made now is counted against the five minutes that follow
    it. The limiter therefore remembers when each request was made, drops the ones that have
    aged out of the window, and waits whenever the ones still inside it number more than the
    budget allows.

    The wait is not a fixed pause. It is the time until the oldest request in the window
    leaves it, because that is the earliest moment a request could be issued without
    exceeding the ceiling. Sleeping for a fixed interval instead would either exceed the
    limit under load or waste the window's remaining capacity when the queue is short.
    """

    def __init__(self, limit: int = RATE_LIMIT, window: float = RATE_WINDOW,
                 target: float = RATE_TARGET) -> None:
        self.limit = int(limit * target)
        self.window = window
        self._stamps: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._stamps = [t for t in self._stamps if now - t < self.window]
                if len(self._stamps) < self.limit:
                    self._stamps.append(now)
                    return
                wait = self.window - (now - self._stamps[0]) + 0.5
            time.sleep(max(wait, 0.5))


class RestUploader:
    """Uploads objects through the store's HTTP API, several at a time.

    A refused request is retried rather than given up on, because the refusal is a rate
    limit rather than a verdict on the request: the same file succeeds later, and the
    alternative — recording it as failed — means the publish never completes.
    """

    def __init__(self, bucket: str, account: str, token: str, workers: int = 12,
                 limiter: RateLimiter | None = None) -> None:
        self.bucket = bucket
        self.account = account
        self.token = token
        self.workers = workers
        self.limiter = limiter or RateLimiter()
        # Set once the token has been found unrenewable. Every worker shares this uploader, so
        # the first refusal after that is answered from here instead of each file asking the
        # service the same question again.
        self.renewal_failed = False
        self.base = (
            f"https://api.cloudflare.com/client/v4/accounts/{account}"
            f"/r2/buckets/{bucket}/objects"
        )

    def put(self, key: str, payload: bytes, content_type: str) -> tuple[str, bool, str]:
        url = f"{self.base}/{key}"
        detail = ""
        for attempt in range(6):
            request = urllib.request.Request(
                url,
                data=payload,
                method="PUT",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": content_type,
                },
            )
            self.limiter.acquire()
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    body = json.loads(response.read())
                etag = body.get("result", {}).get("etag", "")
                return key, True, etag
            except urllib.error.HTTPError as error:
                detail = f"{error.code} {error.read().decode()[:200]}"
                if error.code == 429:
                    # The window is full. Waiting it out is the only thing that helps, so
                    # the pause grows with the number of attempts.
                    time.sleep(RATE_WINDOW / 6 * (attempt + 1))
                    continue
                if error.code in (401, 9109):
                    # The token expired mid-run, which a batch that outlives the grant
                    # will hit sooner or later. Renewing it and trying again is right.
                    if self.renewal_failed:
                        return key, False, detail
                    renewed = refresh_token()
                    if renewed:
                        self.token = renewed
                        continue
                    self.renewal_failed = True
                    return key, False, detail
                return key, False, detail
            except Exception as error:  # noqa: BLE001 - network failures are reported, not raised
                # An interrupted connection says nothing about the request, and the proxy
                # in front of this machine does drop them from time to time. Retrying is
                # what distinguishes a transient drop from a file the store will not take:
                # the retry either succeeds or fails the same way, and either answer is
                # more useful than reporting the first drop as the outcome.
                detail = str(error)[:200]
                if attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                return key, False, detail
        return key, False, detail


def upload_with_rest(
    uploader: RestUploader,
    files: list[tuple[str, Path]],
    state_path: Path | None,
    *,
    dry_run: bool = False,
    index_keys: frozenset[str] = frozenset(),
) -> tuple[int, int]:
    """Upload every file, skipping the ones a previous run already stored.

    The skip list records the size and the store's own entity tag, so a file that changed
    on disk is uploaded again and a file that did not is not.

    The index files named in `index_keys` are held back until every coordinate file has
    been stored. An index that names a file the store does not have is worse than an index
    that is merely out of date: the first produces a viewer that fails on a structure the
    site claims exists, while the second produces one that correctly says the structure has
    not been predicted yet.
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

    coordinates = [(k, p) for k, p in pending if k not in index_keys]
    indexes = [(k, p) for k, p in pending if k in index_keys]

    failures: list[tuple[str, str]] = []
    done = 0
    started = time.time()

    def upload_all(batch: list[tuple[str, Path]]) -> None:
        nonlocal done
        if not batch:
            return
        with concurrent.futures.ThreadPoolExecutor(max_workers=uploader.workers) as pool:
            futures = {
                pool.submit(
                    uploader.put,
                    key,
                    path.read_bytes(),
                    content_type_for(path),
                ): (key, path)
                for key, path in batch
            }
            for future in concurrent.futures.as_completed(futures):
                key, path = futures[future]
                _, ok, detail = future.result()
                done += 1
                if ok:
                    state[key] = [path.stat().st_size, detail]
                else:
                    failures.append((key, detail))
                if done % 200 == 0 or done == len(batch):
                    rate = done / max(time.time() - started, 1e-6)
                    print(f"  {done}/{len(batch)} uploaded ({rate:.1f}/s)", flush=True)

    upload_all(coordinates)

    # The index goes last, and only if every coordinate file it names is in the store.
    if indexes and not failures:
        upload_all(indexes)
    elif indexes:
        print(
            "index withheld: some coordinate files failed to upload, so the index would "
            "name structures the store does not have",
            file=sys.stderr,
        )

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

    token = read_oauth_token()
    expiry = token_expiry()
    if expiry is not None and expiry <= datetime.now(timezone.utc) + timedelta(minutes=10):
        # Renew before the first request rather than after the first refusal, so a long
        # upload does not discover the problem halfway through.
        renewed = refresh_token()
        if renewed:
            token = renewed
        elif expiry <= datetime.now(timezone.utc):
            # An already-expired token refuses every request. Sending a few thousand files
            # to be told so costs minutes and leaves the index withheld anyway, so the round
            # ends here and the staged files wait for a person.
            print(
                "the Cloudflare token has expired and could not be renewed; nothing was "
                "uploaded this round and the files stay staged until `wrangler login` is "
                "run by hand",
                file=sys.stderr,
            )
            return 1

    uploader = RestUploader(args.bucket, args.account, token, args.workers)
    skipped, uploaded = upload_with_rest(
        uploader,
        files,
        args.state,
        dry_run=args.dry_run,
        index_keys=frozenset({"structures.json", "structure_lookup.json"}),
    )
    print(f"published: {uploaded} uploaded, {skipped} already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
