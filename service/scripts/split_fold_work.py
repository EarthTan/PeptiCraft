"""Divide the remaining structures between a large machine and a small one.

    python scripts/split_fold_work.py \
        --manifest ../exports/PeptiCraft-OmegaFold-Pack-20261102/manifest.csv \
        --fasta ../exports/PeptiCraft-OmegaFold-Pack-20261102/fasta/all_by_length.fasta \
        --done ~/done_ids.txt \
        --out ../exports/PeptiCraft-OmegaFold-Pack-20261102/fasta/pair

Why the division is not even
----------------------------
The small machine holds 8 GB of video memory against the large one's 47 GB, so the two long
scaffolds — 971 and 1,097 residues — do not fit at all and stay on the large machine. That
leaves the five shorter scaffolds, and among those the small machine is not uniformly slower:
a 69-residue chain takes five times as long as it does on the large one, a 500-residue chain
three times. Smaller subbatch settings, forced by the memory ceiling, account for part of it;
the rest is the card itself.

A chain is worth handing over when the hours it saves the large machine exceed the hours it
costs the small one, and that ratio improves with length. So the small machine takes the
longest of the short chains — the band where it is least handicapped — and the large machine
keeps everything else. Both then finish within a day of each other.

The split is disjoint and fixed once written: a structure's identifier appears in exactly one
of the four files, so the two machines can never fold the same thing.

Assumptions this rests on, all measured on the hardware in question
-------------------------------------------------------------------
    large machine   24 h/day
    small machine   15 h/day, daytime only
    slow down       interpolated from 69->5.1x, 251->4.1x, 492->2.9x

Change the hours and the fraction moves with them; the constant below records what was used
when the split was written, not a law.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

FIT_A = 7.06e-05
FIT_B = 2.3467

MEASURED = [(69, 5.12), (251, 4.06), (492, 2.93)]
LONG_THRESHOLD = 700
SMALL_SHARE = 0.55


def big_hours(length: int) -> float:
    return FIT_A * (length**FIT_B)


def slowdown(length: int) -> float:
    """How much longer the small machine takes, relative to the large one."""
    if length <= MEASURED[0][0]:
        return MEASURED[0][1]
    if length >= MEASURED[-1][0]:
        return MEASURED[-1][1]
    for (l1, s1), (l2, s2) in zip(MEASURED, MEASURED[1:]):
        if l1 <= length <= l2:
            f = (math.log(length) - math.log(l1)) / (math.log(l2) - math.log(l1))
            return s1 + f * (s2 - s1)
    return MEASURED[-1][1]


def read_manifest(path: Path) -> dict[str, tuple[int, int]]:
    tiers: dict[str, tuple[int, int]] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            sid = row["structure_id"]
            if sid not in tiers:
                tiers[sid] = (int(row["tier"]), int(row["fused_length"]))
    return tiers


def read_sequences(path: Path) -> dict[str, str]:
    sequences: dict[str, str] = {}
    current = None
    chunks: list[str] = []
    for line in path.open():
        line = line.strip()
        if line.startswith(">"):
            if current:
                sequences[current] = "".join(chunks)
            current = line[1:].split()[0]
            chunks = []
        elif current:
            chunks.append(line)
    if current:
        sequences[current] = "".join(chunks)
    return sequences


def write(path: Path, ids, tiers, sequences, hours_per_day: float, scale) -> float:
    ids = sorted(ids, key=lambda s: (tiers[s][1], s))
    with path.open("w") as handle:
        for sid in ids:
            handle.write(f">{sid}\n{sequences[sid]}\n")
    hours = sum(big_hours(tiers[s][1]) * scale(tiers[s][1]) for s in ids) / 3600
    print(f"  {path.name:<16}{len(ids):>7,} 条  {hours:>8.1f} h  → {hours / hours_per_day:>5.1f} 天")
    return hours


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--fasta", required=True, type=Path)
    parser.add_argument("--done", type=Path, default=None, help="identifiers already folded")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--share", type=float, default=SMALL_SHARE,
                        help="fraction of the short chains the small machine takes")
    parser.add_argument("--small-hours-per-day", type=float, default=15.0)
    parser.add_argument("--big-hours-per-day", type=float, default=24.0)
    args = parser.parse_args()

    tiers = read_manifest(args.manifest)
    sequences = read_sequences(args.fasta)
    done = set()
    if args.done and args.done.is_file():
        done = {line.strip().removesuffix(".pdb") for line in args.done.open() if line.strip()}

    args.out.mkdir(parents=True, exist_ok=True)
    remaining = [s for s in tiers if s not in done]
    short = sorted([s for s in remaining if tiers[s][1] <= LONG_THRESHOLD],
                   key=lambda s: (-tiers[s][1], s))
    small = set(short[: int(len(short) * args.share)])

    print(f"未跑 {len(remaining):,} 条，其中短骨架 {len(short):,} 条；"
          f"小机取最长 {len(small):,} 条")
    one = lambda _length: 1.0
    small_hours = (
        write(args.out / "small_p1.fasta", [s for s in small if tiers[s][0] in (1, 2)],
              tiers, sequences, args.small_hours_per_day, slowdown)
        + write(args.out / "small_p2.fasta", [s for s in small if tiers[s][0] == 3],
                tiers, sequences, args.small_hours_per_day, slowdown)
    )
    big_hours_total = (
        write(args.out / "big_p1.fasta",
              [s for s in remaining if s not in small and tiers[s][0] in (1, 2)],
              tiers, sequences, args.big_hours_per_day, one)
        + write(args.out / "big_p2.fasta",
                [s for s in remaining if s not in small and tiers[s][0] == 3],
                tiers, sequences, args.big_hours_per_day, one)
    )
    print(f"\n  合计 {big_hours_total / args.big_hours_per_day:.1f} 天 / "
          f"{small_hours / args.small_hours_per_day:.1f} 天")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
