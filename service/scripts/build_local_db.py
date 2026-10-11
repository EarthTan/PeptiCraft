#!/usr/bin/env python3
"""Build (or rebuild) the local SQLite fixture the fallback backend serves.

    python3 service/scripts/build_local_db.py            # build if absent
    python3 service/scripts/build_local_db.py --force    # delete and rebuild
    python3 service/scripts/build_local_db.py --path /tmp/x.sqlite3
    python3 service/scripts/build_local_db.py --force --with-reference

The fixture is four seeded constructs, not pipeline data; see local/fixture_local.sql. The
service builds it on demand the first time the fallback is used, so running this by hand is
only needed to rebuild it after editing the SQL.

`--with-reference` additionally loads the curated scaffold library from
`resouces/scaffold_database_2026-09-06/` into the new database, so the scaffold the interface
shows on a machine that cannot reach the project database is the real one rather than the two
placeholder rows in the base file. It is opt-in because the test suite builds a database from
the same SQL and counts what is in it; see `scripts/import_scaffold_library.py --target sqlite`.

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
    parser.add_argument(
        "--with-reference",
        action="store_true",
        help="also load the curated scaffold library from resouces/ into the new database",
    )
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
    if args.with_reference:
        _load_reference(target)
    return _report(target)


def _load_reference(target: Path) -> None:
    """Load the curated scaffold library from `resouces/` into a freshly built database.

    Kept out of the plain build deliberately. The test suite builds its own database from the
    same SQL and asserts what it holds, so the curated rows cannot live in the base file
    without making those counts depend on a dataset the team edits on its own schedule. The
    copy made here is the development one: it is what the interface reads when the project
    database is unreachable.
    """
    scripts = Path(__file__).resolve().parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from import_scaffold_library import build_rows, read_source, write_sqlite

    clusters, _rows = read_source()
    library_rows, sequence_rows = build_rows(clusters)
    lib_count, seq_count = write_sqlite(str(target), library_rows, sequence_rows)
    print(
        f"  curated reference: scaffold_library={lib_count} rows, "
        f"scaffold_library_sequences={seq_count} rows"
    )


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
