"""Linker view assembly, across both linker tables.

Two tables hold linkers and they disagree about two column names. The curated
`linker_library` stores a text band in `rigidity` and an index in `rigidity_index`; the
sample `linkers` table stores a numeric 0.0/1.0 in `rigidity` and no band at all. Both
shapes arrive at `to_view`, so the normalisation lives here rather than being written out
once per caller — it previously existed twice, once in the linker router and once in the
construct service, with the two copies reading different keys.

`source_table` is required on every row this module produces. The repository's own
docstring already states that contract ("each row records which of the two it came from"),
and one of its three queries was not selecting the column, so a row that arrived through
that path could not have been rendered.

The listing order is decided here rather than in SQL, for two reasons recorded at
`list_views`: the order is a recommendation about assembly and belongs with the other
judgements in the service, and it has to come out the same on both backends.
"""
from __future__ import annotations

import json
from typing import Any

from ..models.linker import LinkerDetail, LinkerUnit, LinkerView
from ..repositories import linkers as repo
from . import linker_priority as priority


def units(raw: Any) -> list[LinkerUnit]:
    """`unit_composition` arrives as JSONB from Postgres and as text from SQLite."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    return [LinkerUnit(**u) for u in (raw or []) if isinstance(u, dict)]


def band(value: Any) -> str:
    """Map a stored rigidity value onto the five-band label the frontend declares.

    The sample table stores 0.0 for fully flexible and 1.0 for fully rigid. That is a
    coarse two-value convention rather than a measured property, and the five-band
    vocabulary is a presentation choice layered on top of it — `LinkerDetail.rigidity_index`
    carries the raw number so the distinction stays visible.
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "Flexible"
    if f <= 0.0:
        return "Flexible"
    if f >= 1.0:
        return "Rigid"
    return "Balanced"


def to_view(row: dict[str, Any]) -> LinkerView:
    """One linker row, from either table, as the shape the API serves.

    The recommendation travels with the view. A reason already in the library's own
    `priority_reason` column wins over the one in `linker_priority.py`, so a curation decision
    recorded against the row is never overwritten by the table's default reasoning; the table
    fills the field in only where the column is empty, which in this database is every curated
    row.
    """
    rigidity = row.get("rigidity_label")
    if not rigidity:
        flexibility = row.get("flexibility")
        if flexibility is None:
            flexibility = row.get("rigidity")
        rigidity = band(flexibility)
    sequence = row["sequence"]
    source_table = row["source_table"]
    stored_reason = (row.get("priority_reason") or "").strip() or None
    return LinkerView(
        id=row["id"],
        name=row["name"],
        sequence=sequence,
        length=row["length"],
        rigidity=rigidity,
        source_table=source_table,
        unit_composition=units(row.get("unit_composition")),
        description=row.get("description"),
        reference=row.get("reference"),
        priority_rank=priority.rank_for(sequence, source_table),
        priority_reason=stored_reason or priority.reason_for(sequence, source_table),
    )


def to_detail(row: dict[str, Any]) -> LinkerDetail:
    base = to_view(row)
    return LinkerDetail(
        **base.model_dump(),
        flexible_count=row.get("flexible_count"),
        rigid_count=row.get("rigid_count"),
        rigidity_index=_as_float(row.get("flexibility")),
    )


def list_views(include_placeholder: bool = False) -> list[LinkerView]:
    """The library in recommendation order, most suitable first.

    This order is what the Builder displays and what its standing choice is taken from, so it is
    a statement about the entries whether or not it was meant as one. `linker_priority.py` owns
    the statement; the repository's own sort stays underneath as the order for entries the table
    does not cover, and `sorted` is stable so that tail keeps its relative order rather than
    being reshuffled.
    """
    views = [to_view(r) for r in repo.list_linkers(include_placeholder=include_placeholder)]
    return sorted(views, key=lambda v: (v.priority_rank is None, v.priority_rank or 0))


def view_for(linker_id: str | None) -> LinkerView | None:
    """Resolve an id to a view, or None when it names nothing.

    The curated library is searched first and the sample table second, so a caller can
    name either; `source_table` on the result says which one answered. Deciding whether an
    unknown id is an error belongs to the router, which is the layer that reports it.
    """
    if not linker_id:
        return None
    row = repo.get_linker(linker_id)
    return to_view(row) if row else None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
