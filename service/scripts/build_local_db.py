#!/usr/bin/env python3
"""Build (or rebuild) the local SQLite fixture the fallback backend serves.

    python3 service/scripts/build_local_db.py            # build if absent
    python3 service/scripts/build_local_db.py --force    # delete and rebuild
    python3 service/scripts/build_local_db.py --path /tmp/x.sqlite3

The fixture is two seeded constructs, not pipeline data; see local/fixture_local.sql. The
service builds it on demand the first time the fallback is used, so running this by hand is
only needed to rebuild it after editing the SQL.

It prints what it built so the contents are checkable without opening sqlite3.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="delete an existing database first")
    parser.add_argument("--path", default=None, help="override the database path")
    args = parser.parse_args()

    settings = get_settings()
    target = Path(args.path).expanduser() if args.path else settings.sqlite_file
    fixture = settings.sqlite_fixture_file

    if target.exists():
        if not args.force:
            print(f"{target} already exists; pass --force to rebuild")
            return _report(target)
        target.unlink()
        print(f"removed {target}")

    if not fixture.exists():
        print(f"fixture SQL not found: {fixture}", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    try:
        conn.executescript(fixture.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()

    print(f"built {target} from {fixture}")
    return _report(target)


def _report(path: Path) -> int:
    conn = sqlite3.connect(str(path))
    try:
        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        ]
        print("tables:", ", ".join(tables))
        for label, sql in (
            ("constructs", "SELECT id, direction, channel, status, backbone_id, linker_id FROM constructs ORDER BY id"),
            ("backbones", "SELECT id, name, length FROM backbone_proteins ORDER BY id"),
            ("scaffolds", "SELECT id, short_name, length_aa FROM scaffold_library ORDER BY id"),
            ("linkers (sample)", "SELECT id, name, sequence, length FROM linkers ORDER BY id"),
            ("linkers (curated)", "SELECT id, name, length, rigidity FROM linker_library ORDER BY length, name"),
            ("enrichment rows", "SELECT count(*) FROM peptide_enrichment"),
        ):
            print(f"  {label}:")
            for row in conn.execute(sql):
                print("   ", row)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
