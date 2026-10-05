#!/usr/bin/env python3
"""Import the linker library into `linker_library`.

The data came from app/src/data/linkers.ts by way of scripts/extract_linkers.mjs, which
evaluates that module and prints it as JSON. Nothing is retyped here.

    ⚠ That source file no longer exists, so this script cannot currently run — the extractor
    explains what is missing and what would restore it. The 15 rows remain in the
    `linker_library` table, so the data itself is not lost; only the curated source is. See
    the extractor's header before changing anything here.

Two inconsistencies in the source are carried through rather than corrected, because
quietly repairing a curated library would hide the fact that it needs a decision:

  * `(EAAAK)₂` (10 aa) is absent. The library has GGGGS at 1-5 repeats but EAAAK at
    1, 3, 4 and 5 — the 2-repeat rigid entry was never added, so the two families are not
    symmetric.
  * `LK_SAP` carries the sequence `SAP` (3 aa) while its provenance comments describe an
    α-helical SAP linker of 20 aa. The stored sequence and the described one disagree.

Both are surfaced by `scripts/verify_mapping.py` so they are visible rather than buried.

    python3 service/scripts/import_linker_library.py --dry-run
    python3 service/scripts/import_linker_library.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parent
sys.path.insert(0, str(SERVICE_ROOT))

import psycopg  # noqa: E402

from app.config import get_settings  # noqa: E402

EXTRACTOR = SERVICE_ROOT / "scripts" / "extract_linkers.mjs"
SOURCE_VERSION = "2026-09-17"

UPSERT_SQL = """
INSERT INTO linker_library (
    id, name, sequence, length, rigidity, flexible_count, rigid_count, rigidity_index,
    unit_composition, description, reference, priority_reason, source_table,
    source_version, updated_at
) VALUES (
    %(id)s, %(name)s, %(sequence)s, %(length)s, %(rigidity)s, %(flexible_count)s,
    %(rigid_count)s, %(rigidity_index)s, %(unit_composition)s, %(description)s,
    %(reference)s, %(priority_reason)s, 'linker_library', %(source_version)s, now()
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    sequence = EXCLUDED.sequence,
    length = EXCLUDED.length,
    rigidity = EXCLUDED.rigidity,
    flexible_count = EXCLUDED.flexible_count,
    rigid_count = EXCLUDED.rigid_count,
    rigidity_index = EXCLUDED.rigidity_index,
    unit_composition = EXCLUDED.unit_composition,
    description = EXCLUDED.description,
    reference = EXCLUDED.reference,
    priority_reason = EXCLUDED.priority_reason,
    source_version = EXCLUDED.source_version,
    updated_at = now()
"""


def find_node() -> str:
    """Prefer the managed Node runtime, fall back to whatever is on PATH."""
    managed = Path.home() / ".workbuddy" / "binaries" / "node"
    if managed.is_dir():
        for version_dir in sorted(managed.glob("versions/*"), reverse=True):
            candidate = version_dir / "bin" / "node"
            if candidate.is_file():
                return str(candidate)
    return "node"


def extract() -> dict:
    node = find_node()
    result = subprocess.run(
        [node, str(EXTRACTOR)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{node} {EXTRACTOR} failed:\n{result.stderr}")
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = extract()
    linkers = payload["linkers"]
    print(f"source: {payload['source']}  ->  {len(linkers)} linkers")

    rows = []
    for l in linkers:
        rows.append({
            "id": l["id"],
            "name": l["name"],
            "sequence": l["sequence"],
            "length": l["length"],
            "rigidity": l["rigidity"],
            "flexible_count": l["flexible_count"],
            "rigid_count": l["rigid_count"],
            "rigidity_index": l["rigidity_index"],
            # psycopg needs a JSON string for a JSONB parameter
            "unit_composition": json.dumps(l["unit_composition"], ensure_ascii=False),
            "description": l["description"],
            "reference": l["reference"],
            "priority_reason": l["priority_reason"],
            "source_version": SOURCE_VERSION,
        })

    for r in rows:
        print(f"  {r['id']:18s} {r['name']:16s} len={r['length']:3d} "
              f"{r['rigidity'] or '-':16s} GGGGS={r['flexible_count']} EAAAK={r['rigid_count']}")

    fam = {k: sorted({r["length"] for r in rows if r["name"].startswith(k)}) for k in ("(GGGGS)", "(EAAAK)")}
    for family, lengths in fam.items():
        print(f"  repeat-length coverage {family}: {lengths}")

    if args.dry_run:
        print("dry run; nothing written")
        return 0

    settings = get_settings()
    with psycopg.connect(settings.dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, rows)
        conn.commit()
        total = conn.execute("SELECT count(*) FROM linker_library").fetchone()[0]
    print(f"committed: linker_library={total} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
