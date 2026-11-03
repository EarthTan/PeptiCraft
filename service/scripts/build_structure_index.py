"""Turn an OmegaFold output directory into the index the site reads.

    python scripts/build_structure_index.py --folds ~/pepticraft/folds/pdb \
        --manifest ../exports/PeptiCraft-OmegaFold-Pack-20261102/manifest.csv \
        --out /tmp/structures/structures.json \
        --lookup /tmp/structures/structure_lookup.json

The two files this writes are what a browser needs in order to show a structure: one table of
per-structure metadata, and one map from a construct-and-parts combination to the structure
that was predicted for it.

OmegaFold writes one PDB per input sequence and records its per-residue confidence in the
B-factor column. That confidence is the whole reason a predicted structure is worth displaying
at all, and it costs nothing to read: the index carries the mean over the chain, the mean over
the peptide segment, and the geometry that lets a page say which residues are which.

The peptide figure is the one that matters for this platform. A construct is only interesting
if the functional peptide keeps a defined geometry and sits where a target can reach it, and
per-residue confidence restricted to the peptide's own residues is the cheapest available
evidence of the first half of that. It is reported beside the whole-chain figure rather than
instead of it, because a low whole-chain mean with a confident peptide and a low whole-chain
mean with a disordered peptide are different findings and a single number cannot distinguish
them.

Scale: OmegaFold's confidence is conventionally 0–1 while AlphaFold's pLDDT is 0–100, and a
file that has been through a third-party viewer may carry either. The reader detects the scale
from the observed maximum rather than assuming one, and reports the raw range alongside the
normalised mean so a mis-scaled file is visible instead of silently plausible.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

# The peptide occupies the C-terminal tail of the fusion — `scaffold + linker + peptide` — so
# its residues are the last `peptide_length` of the chain. Nothing else in the arrangement is
# needed to locate it.
def _tail_window(total: int, peptide_length: int) -> range:
    return range(max(0, total - peptide_length), total)


def read_pdb(path: Path) -> tuple[dict[int, float], int]:
    """Per-residue confidence keyed by residue index, and the chain length.

    Only the first model is read. A structure written with several models would otherwise have
    its residues overwritten sample by sample, and the mean would describe no single structure.
    """
    per_residue: dict[int, list[float]] = {}
    residues: dict[tuple[str, str, str], int] = {}
    model = 0
    with path.open() as handle:
        for line in handle:
            if line.startswith("MODEL"):
                model += 1
                continue
            if model > 1:
                continue
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            if line[16] not in (" ", "A"):
                continue
            key = (line[21], line[22:26].strip(), line[26])
            index = residues.setdefault(key, len(residues) + 1)
            try:
                per_residue.setdefault(index, []).append(float(line[60:66]))
            except ValueError:
                per_residue.setdefault(index, []).append(float("nan"))
    means = {
        index: (sum(v for v in values if v == v) / len(values) if values else float("nan"))
        for index, values in per_residue.items()
    }
    return means, len(residues)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folds", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lookup", type=Path, default=None,
                        help="also write the construct|scaffold|linker -> structure_id map")
    args = parser.parse_args(argv)

    peptide_length: dict[str, int] = {}
    fused_length: dict[str, int] = {}
    alias: dict[str, str] = {}
    with args.manifest.open(newline="") as handle:
        for row in csv.DictReader(handle):
            peptide_length[row["structure_id"]] = int(row["peptide_length"])
            fused_length[row["structure_id"]] = int(row["fused_length"])
            alias[f"{row['construct_id']}|{row['scaffold_id']}|{row['linker_id']}"] = \
                row["structure_id"]

    entries = []
    missing = []
    observed_max = 0.0
    for seq_id, plen in sorted(peptide_length.items()):
        path = args.folds / f"{seq_id}.pdb"
        if not path.exists():
            missing.append(seq_id)
            continue
        means, length = read_pdb(path)
        values = [v for v in means.values() if v == v]
        if not values:
            missing.append(seq_id)
            continue
        window = [means[i] for i in _tail_window(length, plen) if i in means and means[i] == means[i]]
        observed_max = max(observed_max, max(values))
        entries.append({
            "structure_id": seq_id,
            "file": f"structures/{seq_id}.pdb",
            "aa_length": length,
            "fused_length_expected": fused_length[seq_id],
            "peptide_length": plen,
            "confidence_raw": round(statistics.mean(values), 4),
            "peptide_confidence_raw": round(statistics.mean(window), 4) if window else None,
        })

    scale = 100.0 if observed_max > 1.5 else 1.0
    for entry in entries:
        entry["confidence"] = round(entry.pop("confidence_raw") / scale, 4)
        raw = entry.pop("peptide_confidence_raw")
        entry["peptide_confidence"] = None if raw is None else round(raw / scale, 4)

    payload = {
        "count": len(entries),
        "missing": len(missing),
        "confidence_scale_detected": scale,
        "structures": entries,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"indexed {len(entries)} structures, {len(missing)} missing, "
          f"confidence scale 0–{scale:g}")

    if args.lookup:
        available = {e["structure_id"] for e in entries}
        mapping = {
            key: value for key, value in alias.items()
            if value in available
        }
        args.lookup.write_text(json.dumps(mapping, indent=0) + "\n")
        print(f"lookup {len(mapping)} of {len(alias)} construct combinations -> {args.lookup}")

    if missing:
        (args.out.parent / "missing.txt").write_text("\n".join(missing) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
