"""A local SQLite stand-in for the remote Postgres instance.

The production database lives on an Ubuntu workstation behind a tunnel, so it is not always
reachable from a development machine. Without a fallback every layer above the repositories
would be untestable whenever that host is down, which is exactly when the service most needs
to be worked on. This module serves the same repositories from a small SQLite file that is
built from `local/fixture_local.sql` on first use and holds four seeded constructs.

There are three Postgres constructs the repositories use, and each is translated rather than
removed, because removing one would change the value rather than its representation. A
statement that uses something outside the set raises rather than silently returning the wrong
rows.

Three rules keep this honest:

  * The fixture is *fixture data*. It exists to exercise code paths, not to stand in for
    pipeline output, and `ping()` says so in the value it returns.
  * The connection is opened read-only, matching the read-only sessions the Postgres pool
    hands out. Nothing in the service can write to the fixture through this module.
  * Only the dialect is translated. Thresholds, weights and verdicts are untouched: they
    live in the service layer and do not know which backend answered.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .config import get_settings

log = logging.getLogger("pepticraft.db.sqlite")

# Columns the Postgres schema stores as `jsonb` or as a `text[]`. psycopg decodes both into
# Python objects, so the SQLite rows have to be decoded here as well or a caller that expects
# a list (the scaffold `route_ids`, for one) would receive a string and silently iterate over
# its characters.
JSON_COLUMNS = frozenset({
    "scores",
    "delivery_scores",
    "details",
    "unit_composition",
    "application_tags",
    "route_ids",
    "material_forms",
    "registrations",
})

# `= ANY(%s)` — psycopg binds a list and Postgres expands it. SQLite has no such operator, so
# the list is expanded into an `IN` list and the bound value is spliced into the parameters.
_ANY_RE = re.compile(r"\s*=\s*ANY\s*\(\s*%s\s*\)", re.IGNORECASE)

# `route_ids @> ARRAY[%s]::text[]` — array containment, used by the one query that narrows
# scaffolds by application route. The SQLite column holds a JSON array, so containment is an
# `EXISTS` over `json_each` rather than an operator.
_ARRAY_CONTAINS = "route_ids @> ARRAY[%s]::text[]"
_ARRAY_CONTAINS_SQLITE = (
    "EXISTS (SELECT 1 FROM json_each(scaffold_library.route_ids) AS je WHERE je.value = %s)"
)

# Postgres type casts. The only one the repositories rely on is `::text`, and it is not
# cosmetic — `linkers.id` is an integer column and `id::text` is what makes the response
# carry a string id. It is therefore translated to `CAST(... AS TEXT)` rather than dropped.
# `::text[]` has no SQLite equivalent, so casting to an array is refused outright; the one
# query that used it is rewritten to a `json_each` lookup before this runs.
_CAST_TEXT_RE = re.compile(
    r"(?P<expr>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?|NULL|'(?:[^']*)')"
    r"\s*::\s*text(\[\])?"
)

_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Fixture lifecycle
# ---------------------------------------------------------------------------

def ensure_fixture() -> Path:
    """Build the fixture database from its SQL if it is not already on disk."""
    settings = get_settings()
    path = settings.sqlite_file
    if path.exists():
        return path

    source = settings.sqlite_fixture_file
    if not source.exists():
        raise FileNotFoundError(
            f"local fallback database {path} is missing and its source {source} was not "
            f"found; the SQLite backend cannot start"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    script = source.read_text(encoding="utf-8")
    with _lock:
        # A second request may have built it while this one was waiting for the lock.
        if path.exists():
            return path
        log.warning("building local fallback database at %s from %s", path, source)
        conn = sqlite3.connect(str(path))
        try:
            conn.executescript(script)
            conn.commit()
        finally:
            conn.close()
    return path


# ---------------------------------------------------------------------------
# Dialect translation
# ---------------------------------------------------------------------------

def _translate(sql: str, params: Sequence[Any] | dict[str, Any] | None) -> tuple[str, list[Any]]:
    """Turn one Postgres statement into an equivalent SQLite statement.

    Positional `%s` placeholders become `?`; a list bound to `= ANY(%s)` is expanded into an
    `IN` list; array containment becomes a `json_each` lookup; `::text` becomes
    `CAST(... AS TEXT)`. Anything left untranslated raises rather than reaching SQLite.
    """
    if isinstance(params, dict):
        raise NotImplementedError(
            "the SQLite fallback binds positional parameters only; named parameters are "
            "used nowhere in this service and are not translated"
        )
    bound = list(params or [])

    sql = sql.replace(_ARRAY_CONTAINS, _ARRAY_CONTAINS_SQLITE)

    out: list[str] = []
    new_params: list[Any] = []
    pi = 0
    pos = 0

    def take() -> Any:
        nonlocal pi
        value = bound[pi] if pi < len(bound) else None
        pi += 1
        return value

    while pos < len(sql):
        # Take whichever comes first: an `= ANY(%s)` list expansion or a plain `%s`.
        # The ANY pattern must be checked with `search` rather than `match`, because `pos`
        # walks the string token by token and does not stop on the `=` that starts it.
        m = _ANY_RE.search(sql, pos)
        j = sql.find("%s", pos)

        if m is not None and (j == -1 or m.start() <= j):
            out.append(sql[pos:m.start()])
            value = take()
            if isinstance(value, (list, tuple, set, frozenset)):
                items = list(value)
                if items:
                    out.append(" IN (" + ", ".join("?" for _ in items) + ")")
                    new_params.extend(items)
                else:
                    # An empty set matches nothing; `IN (NULL)` evaluates to NULL, never true.
                    out.append(" IN (NULL)")
            else:
                out.append(" = ?")
                new_params.append(value)
            pos = m.end()
            continue

        if j == -1:
            out.append(sql[pos:])
            break
        out.append(sql[pos:j])
        out.append("?")
        new_params.append(take())
        pos = j + 2

    text = "".join(out)

    def _cast(match: re.Match[str]) -> str:
        if match.group(2):
            raise NotImplementedError(
                "`::text[]` cannot be translated to SQLite; rewrite the statement to use "
                f"`json_each` instead. Offending match: {match.group(0)!r}"
            )
        return f"CAST({match.group('expr')} AS TEXT)"

    text = _CAST_TEXT_RE.sub(_cast, text)
    if "::" in text:
        raise NotImplementedError(
            f"untranslated PostgreSQL type cast in statement: {text!r}"
        )
    return text, new_params


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row, columns: Sequence[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, name in enumerate(columns):
        value = row[i]
        if name in JSON_COLUMNS and isinstance(value, str):
            stripped = value.lstrip()
            if stripped[:1] in ("[", "{"):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
        out[name] = value
    return out


def query(
    sql: str,
    params: Sequence[Any] | dict[str, Any] | None = None,
    *,
    force_index: bool = False,  # accepted for signature parity; SQLite ignores it
) -> list[dict[str, Any]]:
    """Run one statement and return every row as a dict.

    `force_index` exists so the repositories can call this and the Postgres backend with the
    same signature. The settings it maps to are planner hints for a 377 M-row table and have
    no SQLite equivalent, so it is accepted and ignored.
    """
    settings = get_settings()
    text, bound = _translate(sql, params)

    with _lock:
        conn = sqlite3.connect(str(settings.sqlite_file), timeout=5.0)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            cursor = conn.execute(text, bound)
            rows = cursor.fetchall()
            columns = [d[0] for d in (cursor.description or [])]
        finally:
            conn.close()

    return [_row_to_dict(r, columns) for r in rows]


def ping() -> dict[str, Any]:
    """The liveness payload `/api/health` reads, shaped like the Postgres one."""
    settings = get_settings()
    row = query("SELECT sqlite_version() AS v")
    version = row[0]["v"] if row else "unknown"
    return {
        "version": f"SQLite {version} (local fallback fixture)",
        "db": str(settings.sqlite_file),
        "ts": datetime.now(timezone.utc),
    }
