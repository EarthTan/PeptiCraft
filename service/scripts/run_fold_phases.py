"""Fold the pack in two phases: the linkers the platform offers by default, then the rest.

    python scripts/run_fold_phases.py --pack <pack dir> --out <folds dir>

Why two phases
--------------
The pack enumerates fifteen linkers for every candidate and every reachable scaffold, and
three of those fifteen are different from the other twelve: the linker the library ranks
first, and the one it ranks second. Those two are what the Builder offers when a reader does
not go looking, and they are what a construct page shows by default. The remaining thirteen
are the exhaustive remainder, useful for a completeness claim and for nothing else.

Predicting them in one pass ordered by length spreads the cost across the whole space
evenly, which means the two default linkers are finished only at the very end — after the
whole exhaustive remainder. Running the two default linkers first inverts that: the set a
reader actually reaches is complete in weeks rather than months, and the exhaustive remainder
fills in afterwards, cheapest first.

What each phase costs is a property of the sequences rather than of the ordering. Tier 1 and
tier 2 together are 3,556 distinct structures, and 77% of their fold time belongs to two
long scaffolds. So the first phase is not short: it is the whole tier 1 and tier 2 set, at
every length, including the two scaffolds that take hours each.

Why the phases are just two files
---------------------------------
A phase is a FASTA and nothing else. The batch skips any sequence whose coordinate file
already exists, so the second phase, which is the whole set ordered by length, automatically
picks up whatever the first phase left out — including the sequences the first phase failed
on, because a failure writes no file. The ordering within the first phase is length-ascending
as well, which is the ordering the pack's files already use.

Retrying
--------
A failure is written to no file, so a later pass tries it again. Between the first phase and
the second phase that gap is weeks, which is long enough for a transient failure to look
like a permanent one. Each phase therefore ends with a retry pass over its own failures,
and the retry passes are bounded: a sequence that fails identically twice is not going to
succeed on the fourth attempt, and the loop must not spin on it.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fold_batch import run  # noqa: E402

# The two phases, in order. The first is the cumulative tier 1 and tier 2 set; the second is
# the whole set, which the batch walks in length order and skips what is already folded.
PHASES = [
    ("tier1+2", "tier2_two_linkers.fasta.gz"),
    ("full", "all_by_length.fasta"),
]

# How many times a phase's own failures are retried before the phase gives up on them.
RETRIES = 2


def log(message: str, path: Path) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    with path.open("a") as handle:
        handle.write(line + "\n")


def run_phase(
    name: str,
    fasta: Path,
    out: Path,
    url: str,
    log_path: Path,
    retries: int,
) -> list[str]:
    """Fold one phase, then retry whatever it failed on. Returns the remaining failures.

    The first pass folds everything the phase still owes. The passes after it fold only the
    sequences that failed, named explicitly: a failure writes no coordinate file, so a plain
    second pass would also pick it up, but naming it makes the retry cost exactly the
    failures rather than whatever else the phase has pending.
    """
    remaining: list[str] = []
    for attempt in range(retries + 1):
        retry_file = out / f"retry-{name}.txt"
        if attempt == 0:
            summary = run(str(fasta), str(out), url=url)
        else:
            summary = run(str(fasta), str(out), url=url, retry=str(retry_file))
        remaining = summary["failed"]
        if not remaining:
            log(f"phase {name}: {summary['folded']} folded, no failures", log_path)
            return []
        log(
            f"phase {name}: {summary['folded']} folded, {len(remaining)} failed"
            + (f" (attempt {attempt + 1}/{retries + 1})" if attempt < retries else ""),
            log_path,
        )
        if attempt < retries:
            retry_file.write_text("\n".join(remaining) + "\n")
            log(f"phase {name}: retrying {len(remaining)} sequences", log_path)
    log(f"phase {name}: giving up on {len(remaining)} sequences", log_path)
    return remaining


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", type=Path, required=True, help="the pack directory")
    ap.add_argument("--out", type=Path, required=True, help="where coordinates are written")
    ap.add_argument("--url", default="http://127.0.0.1:8204/predict")
    ap.add_argument("--retries", type=int, default=RETRIES)
    args = ap.parse_args(argv)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "phases.log"

    log(f"starting two-phase fold: pack={args.pack} out={out}", log_path)

    for name, filename in PHASES:
        fasta = args.pack / "fasta" / filename
        if not fasta.exists():
            log(f"phase {name}: missing {fasta}, stopping", log_path)
            return 1
        log(f"phase {name}: {filename}", log_path)
        failures = run_phase(name, fasta, out, args.url, log_path, args.retries)
        if failures:
            log(f"phase {name}: {len(failures)} sequences remain failed", log_path)

    log("all phases complete", log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
