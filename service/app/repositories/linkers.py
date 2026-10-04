"""Read access to the linker library, across both linker tables.

`linkers` (6 rows, sample) and `linker_library` (15 rows, curated) are both read, and each
row records which of the two it came from in `source_table`. A construct's `linker_id`
resolves against `linkers`, so that lookup has to keep working; a linker enumeration in the
Builder should use the curated set. Exposing the origin lets the UI show the difference
instead of silently mixing a six-entry sample with a fifteen-entry library.

Only id-keyed reads are served from here. The construct queries already join `linkers` for
the name, sequence, length, rigidity and description of the row a construct points at, and
`services.constructs.stored_linker_view` builds the view from those columns rather than
re-reading the row — a build assembles one linker per candidate, so a per-row lookup would
turn a single request into one query per row.
"""
from __future__ import annotations

from typing import Any

from .. import db

_LEGACY_SELECT = """
SELECT id::text        AS id,
       name,
       sequence,
       length,
       NULL::text      AS rigidity_label,   -- the sample table stores no band, only a 0/1 value
       rigidity        AS flexibility,
       flexible_count,
       rigid_count,
       description,
       'linkers'::text AS source_table
  FROM linkers
"""

# `unit_composition` and `priority_reason` are selected here because `LinkerDetail` serves
# them. They were absent from the select list, so every linker detail came back with an empty
# unit composition and no priority reason even though the columns are populated — the
# response model promised something the query never fetched.
_LIBRARY_SELECT = """
SELECT id,
       name,
       sequence,
       length,
       rigidity          AS rigidity_label,
       rigidity_index    AS flexibility,
       flexible_count,
       rigid_count,
       unit_composition,
       description,
       reference,
       priority_reason,
       'linker_library'::text AS source_table
  FROM linker_library
"""


def list_linkers(include_placeholder: bool = False) -> list[dict[str, Any]]:
    rows = db.query(f"{_LIBRARY_SELECT} ORDER BY length, name")
    if include_placeholder:
        rows = rows + db.query(f"{_LEGACY_SELECT} ORDER BY length, name")
    return rows


def get_linker(linker_id: str) -> dict[str, Any] | None:
    """Resolve an id against the curated library first, then the sample table.

    Used for a linker a request names, where the curated library is the set a caller is
    choosing from and the sample table is the fallback that keeps an id from the record
    resolvable. A construct's own `linker_id` must not come through here: that id is a
    foreign key to `linkers`, and preferring the library would let a curated entry with a
    numeric id shadow the row the construct actually points at.
    """
    row = db.query_one(f"{_LIBRARY_SELECT} WHERE id = %s", [linker_id])
    if row:
        return row
    if linker_id.isdigit():
        return db.query_one(f"{_LEGACY_SELECT} WHERE id = %s", [linker_id])
    return None
