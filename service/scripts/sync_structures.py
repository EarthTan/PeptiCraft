"""Keep the structure store in step with what the workstation has finished.

    python scripts/sync_structures.py --state ~/.pepticraft-upload-state.json

This is the loop the batch needs. The workstation folds structures over days, and
the site reads them from an object store, so something has to move the finished
files across and rebuild the two index files each time. Running it on a schedule
means the site shows a structure as soon as it exists, rather than at the end of
the run.

What it does, in order:

    1. copy the coordinate files the workstation has finished since the last run
    2. rebuild the index from them
    3. upload what the store does not have yet
    4. upload the two index files, which are rewritten every time

The store is reached through the HTTP API with the OAuth token wrangler holds, so
nothing here needs a separate credential. The upload is incremental: a file that
the store already has at the same size is not sent again, which matters when the
run is twenty-six thousand structures.

The index is uploaded last, on purpose. If the run is interrupted halfway through,
the index on the store still describes the set of structures that are all present,
rather than pointing at coordinates that have not arrived.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_STAGING = Path.home() / "pepticraft-structures"
DEFAULT_STATE = Path.home() / ".pepticraft-upload-state.json"


def pull(remote: str, staging: Path, *, dry_run: bool = False) -> int:
    """Copy the finished coordinate files across, keeping the ones already local."""
    staging.mkdir(parents=True, exist_ok=True)
    command = [
        "rsync", "-az", "--include", "*.pdb", "--exclude", "*",
        f"{remote.rstrip('/')}/", f"{staging}/",
    ]
    if dry_run:
        print(f"[dry-run] {' '.join(command)}")
        return 0
    result = subprocess.run(command)
    if result.returncode != 0:
        raise SystemExit(f"rsync failed ({result.returncode})")
    return len(list(staging.glob("*.pdb")))


def publish(
    staging: Path,
    manifest: Path,
    bucket: str,
    state: Path,
    workers: int,
    *,
    dry_run: bool = False,
) -> None:
    command = [
        sys.executable,
        str(Path(__file__).with_name("publish_structures.py")),
        "--staging", str(staging),
        "--manifest", str(manifest),
        "--bucket", bucket,
        "--state", str(state),
        "--workers", str(workers),
    ]
    if dry_run:
        command.append("--dry-run")
    result = subprocess.run(command)
    if result.returncode != 0:
        raise SystemExit(f"publish failed ({result.returncode})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--remote", default="dku-1387-tailscale:/home/lenovo/pepticraft/folds/pdb",
                        help="where the workstation keeps the finished coordinate files")
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING,
                        help="where to keep them on this machine")
    parser.add_argument("--manifest", type=Path, required=True,
                        help="the pack's manifest.csv")
    parser.add_argument("--bucket", default="pepticraft-structures")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--watch", action="store_true",
                        help="keep running, publishing every --interval minutes")
    parser.add_argument("--interval", type=float, default=30.0,
                        help="minutes between runs when watching")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    while True:
        started = time.time()
        count = pull(args.remote, args.staging, dry_run=args.dry_run)
        print(f"{count} coordinate files locally", flush=True)
        publish(args.staging, args.manifest, args.bucket, args.state, args.workers,
                dry_run=args.dry_run)
        print(f"published in {(time.time() - started) / 60:.1f} min", flush=True)
        if not args.watch:
            return 0
        time.sleep(max(args.interval, 1.0) * 60)


if __name__ == "__main__":
    raise SystemExit(main())
