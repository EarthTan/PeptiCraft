#!/usr/bin/env python3
"""Apply the SQL migrations under service/sql/.

The scripts are idempotent and additive: they create tables that do not exist yet and
never alter or drop anything already in the database. Running this twice is a no-op.

    python3 service/scripts/migrate.py            # apply
    python3 service/scripts/migrate.py --dry-run  # list what would run

Connection comes from the same settings the service uses, so `IGEM_PG_DSN` or the
`IGEM_PG_HOST` / `IGEM_PG_PASSWORD` pair must be set (see service/.env.example).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg  # noqa: E402

from app.config import get_settings  # noqa: E402

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    scripts = sorted(SQL_DIR.glob("*.sql"))
    if not scripts:
        print(f"no .sql files under {SQL_DIR}", file=sys.stderr)
        return 1

    settings = get_settings()
    print(f"target: {settings.igem_pg_host or '(from DSN)'} db={settings.igem_pg_db}")

    if args.dry_run:
        for path in scripts:
            print(f"  would apply {path.name}")
        return 0

    with psycopg.connect(settings.dsn, autocommit=False) as conn:
        for path in scripts:
            print(f"  applying {path.name} ...", end="", flush=True)
            conn.execute(path.read_text(encoding="utf-8"))
            conn.commit()
            print(" ok")
        rows = conn.execute(
            """
            SELECT table_name
              FROM information_schema.tables
             WHERE table_schema = 'public'
               AND table_name IN ('scaffold_library','scaffold_library_sequences','linker_library')
             ORDER BY table_name
            """
        ).fetchall()
    print("present tables:", ", ".join(r[0] for r in rows) or "(none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
