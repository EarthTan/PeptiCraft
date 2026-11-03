"""Enumerate the fusion constructs the static platform can display, and write an OmegaFold pack.

    python scripts/export_omegafold_pack.py --out ../exports/PeptiCraft-OmegaFold-Pack-<date>

Why this exists
---------------
The deployed platform is static files. Ranking, composites and safety verdicts are computed
ahead of time by `export_static.py` and served as JSON, which is affordable because the space
of possible rankings is small — five routes times fifteen non-empty direction subsets, eighty
files. A three-dimensional structure cannot be folded into that arrangement, for a reason that
is arithmetic rather than aesthetic: the count of structures is the product of three
independent choices, while the count of rankings is the product of two small ones.

It also cannot take the shortcut the sequence layer takes. `assembly_recipes` in
`export_static.py` deliberately does not export one fused *sequence* per scaffold-and-linker
pair; it exports the three parts and lets the interface concatenate them, because
concatenation carries no threshold, no weight and no verdict, and a mistake in it shows as a
visibly wrong residue string. A structure is not a concatenation of the structures of its
parts, so there is no equivalent move available here. Every combination has to be predicted,
or the combination is not available.

What this script therefore does is enumerate, de-duplicate and partition. It does not predict:
inference happens on a workstation that is not this machine. What leaves this repository is a
set of FASTA files, a manifest that maps every sequence back to the choices that produced it,
and a runner.

The three inputs, and why each is read from the exported snapshot
----------------------------------------------------------------
The candidate set, the scaffold sequences and the linker sequences are read from
`publish/data`, which is the same directory the site serves. That is the point: a pack built
from the live database could contain a construct the deployed interface cannot reach, or miss
one it can, and the mismatch would not surface until a viewer asked for a structure that was
never predicted. Building from the shipped snapshot makes the pack and the interface the same
set by construction, and the snapshot already carries the resolved scaffolding — eight
clusters, sixteen sequence records, fifteen linkers and the representative-sequence rule.

De-duplication
--------------
A structure is a function of the fused sequence alone. Two constructs whose peptides are the
same string therefore need one prediction, not two, whatever their identifiers or direction
labels say. The count of stored constructs (290) exceeds the count of distinct peptide
sequences (254), and the difference is not noise: twenty-eight peptides recur across
constructs. Keys are content-addressed for that reason — `s<sha1 prefix>` of the fused
sequence — so a repeated sequence collapses to one file and the manifest records every
identifier that resolves to it.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger("pepticraft.omegafold_pack")

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = _REPO_ROOT / "publish" / "data"

# The twenty residue codes, plus nothing else. The pipeline's own earliest source table carried
# SMILES-style annotations in its sequence column, which is why version 1.1 dropped rows on this
# test before anything counted them; the same test here keeps a non-peptide string from becoming
# a Fusion input that OmegaFold would silently sanitise.
RESIDUES = frozenset("ACDEFGHIKLMNPQRSTVWY")

# Below this length a fusion is a chain of the scaffold's residues and little else. The
# prediction still runs and is still recorded; the flag exists so a report can separate a
# structure that says something about the peptide from one that cannot.
SHORT_PEPTIDE = 5


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("ascii")).hexdigest()


def structure_id(sequence: str) -> str:
    """Content-addressed key, and the filename OmegaFold will write.

    The identifier has to survive re-export without pointing at a different molecule, which
    rules out anything derived from a row id. OmegaFold names its output after the FASTA header,
    so the header and the key are the same string by design and no rename step is needed on the
    workstation.
    """
    return "s" + _sha1(sequence)[:16]


def load_scaffolds(data: Path) -> list[dict[str, Any]]:
    """Every scaffold, with its representative sequence and the routes that admit it.

    The representative is the longest variant, which is the rule `services.assembly` applies and
    which `app/src/api/static.ts` repeats in the browser. Reproducing it a third time is a cost;
    the alternative is a pack whose sequences disagree with the interface that displays them.
    """
    out = []
    for summary in json.loads((data / "scaffolds.json").read_text()):
        detail = json.loads((data / "scaffolds" / f"{summary['id']}.json").read_text())
        variants = [s for s in detail.get("sequences") or [] if s.get("sequence")]
        if not variants:
            raise RuntimeError(f"scaffold {summary['id']} carries no sequence")
        rep = max(variants, key=lambda s: len(s["sequence"]))
        out.append({
            "id": summary["id"],
            "short_name": summary["short_name"],
            "length": len(rep["sequence"]),
            "sequence": rep["sequence"],
            "sequence_id": rep.get("sequence_id"),
            "routes": list(summary.get("route_ids") or []),
        })
    return out


def load_linkers(data: Path) -> list[dict[str, Any]]:
    rows = json.loads((data / "linkers.json").read_text())
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "length": len(r["sequence"]),
            "sequence": r["sequence"],
            "priority_rank": r.get("priority_rank"),
        }
        for r in rows
    ]


def load_constructs(data: Path) -> dict[str, dict[str, Any]]:
    """The union of every ranking the site can serve, keyed by construct id.

    Read from the exported rankings rather than from `constructs.json`, because the rankings are
    what carry the candidate set: only the top channel is ranked, and a construct that appears in
    no ranking is not reachable from the Builder however many rows the table holds.
    """
    found: dict[str, dict[str, Any]] = {}
    for path in sorted((data / "builds").glob("*/*.json")):
        for item in json.loads(path.read_text()).get("items") or []:
            found.setdefault(item["id"], {
                "id": item["id"],
                "direction": item["direction"],
                "sequence": item["peptide_sequence"],
                "length": len(item["peptide_sequence"]),
            })
    if not found:
        raise RuntimeError("no ranking files under publish/data/builds; export first")
    return found


def enumerate_combos(
    constructs: Iterable[dict[str, Any]],
    scaffolds: list[dict[str, Any]],
    linkers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Every (construct, scaffold, linker) the interface can ask for, with its fused sequence.

    A scaffold reaches this list when at least one route admits it. One that no route admits
    cannot be chosen in the Builder — `amsilk-eadf4-c16` is in that position, because the source
    table's `Hair care` column has no counterpart route and the import therefore maps it to no
    route at all — so predicting its fusions would spend inference on a molecule the interface
    can never display.
    """
    admitted = [s for s in scaffolds if s["routes"]]
    rows: list[dict[str, Any]] = []
    for construct in constructs:
        peptide = construct["sequence"]
        for scaffold in admitted:
            for linker in linkers:
                fused = f"{scaffold['sequence']}{linker['sequence']}{peptide}"
                rows.append({
                    "construct_id": construct["id"],
                    "direction": construct["direction"],
                    "scaffold_id": scaffold["id"],
                    "scaffold_sequence_id": scaffold["sequence_id"],
                    "scaffold_length": scaffold["length"],
                    "linker_id": linker["id"],
                    "linker_length": linker["length"],
                    "linker_rank": linker["priority_rank"],
                    "peptide_sequence": peptide,
                    "peptide_length": construct["length"],
                    "fused_sequence": fused,
                    "fused_length": len(fused),
                    "routes": ";".join(scaffold["routes"]),
                    "structure_id": structure_id(fused),
                })
    return rows


def tier_of(linker_rank: int | None) -> int:
    """Which release a row belongs to.

    Tier 1 is the linker the library itself ranks first, and it is where a first run should
    stop: it covers every reachable candidate and every reachable scaffold, which is every
    combination a reader can arrive at while leaving the linker at its default. Tier 2 adds the
    second-ranked linker, tier 3 the remaining thirteen.
    """
    if linker_rank == 1:
        return 1
    if linker_rank == 2:
        return 2
    return 3


def write_manifest(rows: list[dict[str, Any]], path: Path) -> None:
    columns = [
        "structure_id", "construct_id", "direction", "scaffold_id",
        "scaffold_sequence_id", "scaffold_length", "linker_id", "linker_length",
        "linker_rank", "tier", "peptide_length", "fused_length", "routes",
        "sequence_sha256", "flag", "peptide_sequence",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                **{k: row[k] for k in columns if k in row},
                "tier": tier_of(row["linker_rank"]),
                "sequence_sha256": hashlib.sha256(
                    row["fused_sequence"].encode("ascii")
                ).hexdigest(),
                "flag": "short_peptide" if row["peptide_length"] < SHORT_PEPTIDE else "",
            })


def write_fasta(records: list[dict[str, Any]], path: Path) -> None:
    """One record per structure, wrapped at 60 columns.

    The header is the structure identifier and nothing else. OmegaFold takes the output filename
    from the first token of the header, so a header carrying extra fields would produce filenames
    the manifest could not predict.
    """
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", newline="\n") as handle:
        for seq_id, sequence in records:
            handle.write(f">{seq_id}\n")
            for i in range(0, len(sequence), 60):
                handle.write(sequence[i:i + 60] + "\n")


def build(data: Path, out: Path, fasta_dir: Path) -> dict[str, Any]:
    scaffolds = load_scaffolds(data)
    linkers = load_linkers(data)
    constructs = load_constructs(data)

    bad = [
        (c["id"], c["sequence"]) for c in constructs.values()
        if not set(c["sequence"]) <= RESIDUES
    ]
    if bad:
        raise RuntimeError(
            "construct peptides outside the twenty-residue alphabet: "
            + ", ".join(f"{i}={s!r}" for i, s in bad[:5])
        )

    rows = enumerate_combos(constructs.values(), scaffolds, linkers)

    # Content-addressed collapse: one prediction per distinct fused sequence, with the first
    # combination that produced it holding the canonical row.
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique.setdefault(row["structure_id"], row)

    write_manifest(rows, out / "manifest.csv")

    for tier in (1, 2, 3):
        selected = [r for r in unique.values() if tier_of(r["linker_rank"]) <= tier]
        selected.sort(key=lambda r: (r["fused_length"], r["structure_id"]))
        name = {1: "tier1_recommended_linker", 2: "tier2_two_linkers",
                3: "tier3_exhaustive"}[tier]
        suffix = ".fasta" if tier == 1 else ".fasta.gz"
        write_fasta([(r["structure_id"], r["fused_sequence"]) for r in selected],
                    fasta_dir / f"{name}{suffix}")
        log.info("tier %d: %d structures -> %s%s", tier, len(selected), name, suffix)

    summary = {
        "generated_from": str(data.relative_to(_REPO_ROOT)),
        "constructs": len(constructs),
        "distinct_peptides": len({c["sequence"] for c in constructs.values()}),
        "scaffolds_reachable": sum(1 for s in scaffolds if s["routes"]),
        "scaffolds_total": len(scaffolds),
        "linkers": len(linkers),
        "combinations": len(rows),
        "distinct_structures": len(unique),
        "tier1": sum(1 for r in unique.values() if tier_of(r["linker_rank"]) == 1),
        "tier2": sum(1 for r in unique.values() if tier_of(r["linker_rank"]) == 2),
        "tier3": sum(1 for r in unique.values() if tier_of(r["linker_rank"]) == 3),
        "fused_length_min": min(r["fused_length"] for r in unique.values()),
        "fused_length_max": max(r["fused_length"] for r in unique.values()),
        "residues_total": sum(r["fused_length"] for r in unique.values()),
        "short_peptide_structures": sum(
            1 for r in unique.values() if r["peptide_length"] < SHORT_PEPTIDE
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA,
                        help="exported static data directory (default: publish/data)")
    parser.add_argument("--out", type=Path, required=True, help="pack directory to write")
    parser.add_argument("--fasta-dir", type=Path, default=None,
                        help="where the FASTA files go (default: <out>/fasta)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    fasta_dir = args.fasta_dir or (args.out / "fasta")
    fasta_dir.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)

    summary = build(args.data, args.out, fasta_dir)
    log.info(
        "combinations=%d distinct=%d tier1=%d tier2=%d tier3=%d residues=%s",
        summary["combinations"], summary["distinct_structures"], summary["tier1"],
        summary["tier2"], summary["tier3"], f"{summary['residues_total']:,}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
