"""Read access to `constructs` and its neighbours.

One query shape carries almost every read path: a construct joined to its peptide, its
scaffold and its linker. Filtering happens in SQL, pagination happens in SQL, and the score
assembly happens in the service layer after the rows are in memory — the stored `scores`
JSONB is heterogeneous across directions, so any attempt to flatten it in SQL would need a
per-direction CASE ladder that duplicates the mapping table.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

from .. import db

# Direction-independent six keys plus the per-direction functional keys. Selecting the
# whole JSONB is cheaper than naming 26 keys and keeps unmodelled keys visible, which
# matters: silently dropping them is how a score goes missing without anyone noticing.
_BASE_SELECT = """
SELECT
    c.id,
    c.direction,
    c.scenario,
    c.backbone_id,
    c.linker_id,
    c.peptide_id,
    c.full_sequence,
    c.channel,
    c.status,
    c.rank,
    c.scores,
    c.delivery_scores,
    c.assessed_hemo,
    c.assessed_mhci,
    c.assessed_mhcii,
    c.created_at,
    p.sequence            AS peptide_sequence,
    p.length              AS peptide_length,
    p.source              AS peptide_source,
    p.source_version      AS peptide_source_version,
    p.source_accession    AS peptide_source_accession,
    p.seq_md5             AS peptide_md5,
    bp.name               AS backbone_name,
    bp.sequence           AS backbone_sequence,
    bp.length             AS backbone_length,
    lk.name               AS linker_name,
    lk.sequence           AS linker_sequence,
    lk.length             AS linker_length,
    lk.rigidity           AS linker_rigidity,
    lk.description        AS linker_description
FROM constructs c
JOIN peptides p            ON p.id = c.peptide_id
LEFT JOIN backbone_proteins bp ON bp.id = c.backbone_id
LEFT JOIN linkers lk       ON lk.id = c.linker_id
"""

_ORDER = {
    "rank": "c.direction, c.channel DESC, c.rank NULLS LAST, c.id",
    "id": "c.id",
    "peptide_length": "sp.length NULLS LAST, c.id",
    "peptide_id": "sp.id",
}

# Sort orders whose expression reads the peptides alias. The alias comes from the search
# join, so an order that needs it has to bring that join in even when no term was typed —
# otherwise `ORDER BY sp.length` would reference an alias the statement never declared.
_ORDER_NEEDS_PEPTIDES = frozenset({"peptide_length", "peptide_id"})

_PEPTIDES_JOIN = "JOIN peptides sp ON sp.id = c.peptide_id"


def _where(
    direction: str | None,
    channel: str | None,
    status: str | None,
    min_rank: int | None,
    search: str | None = None,
) -> tuple[str, list[Any], str]:
    """Build the filter clause, its parameters, and any extra join it needs.

    The search term is the one filter that cannot be answered from `constructs` alone: it
    matches on the peptide's own columns, so a statement carrying it needs a second join to
    `peptides`. That join is returned rather than assumed, so the caller cannot count rows
    against one statement shape and read them from another — a mismatch there would report a
    total the page cannot reconcile with the rows it holds.

    Matching is written as `lower(col) LIKE ...` with an explicit `ESCAPE`, rather than
    `ILIKE`. `ILIKE` is Postgres syntax SQLite does not implement, and this repository has to
    select the same rows against either backend. The `ESCAPE` clause is stated explicitly
    because the two engines disagree on the default: Postgres already reads a backslash as an
    escape, SQLite does not, so without it the same term would match different rows on the
    real database and on the local fixture.
    """
    clauses: list[str] = []
    params: list[Any] = []
    join = ""
    if direction:
        clauses.append("c.direction = %s")
        params.append(direction)
    if channel:
        clauses.append("c.channel = %s")
        params.append(channel)
    if status:
        clauses.append("c.status = %s")
        params.append(status)
    if min_rank is not None:
        clauses.append("c.rank IS NOT NULL AND c.rank <= %s")
        params.append(min_rank)
    if search:
        join = _PEPTIDES_JOIN
        clauses.append(
            "(lower(sp.sequence) LIKE %s ESCAPE '\\'"
            " OR lower(COALESCE(sp.source, '')) LIKE %s ESCAPE '\\'"
            " OR lower(COALESCE(sp.source_accession, '')) LIKE %s ESCAPE '\\'"
            " OR lower(COALESCE(sp.source_version, '')) LIKE %s ESCAPE '\\')"
        )
        # Substring match on a literal term: a peptide sequence is short enough that
        # "contains" is what a reader means, and the metacharacters are escaped so a `%` in
        # the term does not turn the filter into a match-everything pattern.
        pattern = f"%{_escape_like(search)}%"
        params.extend([pattern] * 4)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params, join


def _escape_like(term: str) -> str:
    """Neutralise the LIKE metacharacters in a user-supplied term.

    Paired with `ESCAPE '\\'` on the clause, so `A_B` matches only a literal underscore and
    `100%` matches only a literal percent sign rather than every row.
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_constructs(
    *,
    direction: str | None = None,
    channel: str | None = None,
    status: str | None = None,
    min_rank: int | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    order: str = "rank",
) -> tuple[list[dict[str, Any]], int]:
    where, params, join = _where(direction, channel, status, min_rank, search)
    order_by = _ORDER.get(order, _ORDER["rank"])
    if order in _ORDER_NEEDS_PEPTIDES and not join:
        join = _PEPTIDES_JOIN

    total = db.count(f"SELECT count(*) AS n FROM constructs c {join}{where}", params)
    if total == 0:
        return [], 0

    rows = db.query(
        f"{_BASE_SELECT} {join}{where} ORDER BY {order_by} LIMIT %s OFFSET %s",
        [*params, limit, offset],
    )
    return rows, total


def get_construct(construct_id: int) -> dict[str, Any] | None:
    return db.query_one(f"{_BASE_SELECT} WHERE c.id = %s", [construct_id])


def get_constructs_by_ids(ids: Sequence[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    return db.query(f"{_BASE_SELECT} WHERE c.id = ANY(%s)", [list(ids)])


def direction_counts() -> list[dict[str, Any]]:
    """Real counts per direction.

    The frontend previously hardcoded these as antioxidant 250 / antimicrobial 250 /
    anti-inflammatory 0 / anti-melanin 0. The actual distribution is 170 / 65 / 154 / 107,
    which is wrong in two different ways at once: the two directions shown as ready-and-full
    are off by a factor of four, and the two shown as empty hold 261 rows between them.
    """
    return db.query(
        """
        SELECT c.direction,
               c.channel,
               c.status,
               count(*) AS n
          FROM constructs c
         GROUP BY c.direction, c.channel, c.status
         ORDER BY c.direction, c.channel, c.status
        """
    )


def scaffold_binding_counts() -> list[dict[str, Any]]:
    """Which scaffolds the stored constructs actually point at."""
    return db.query(
        """
        SELECT c.backbone_id,
               bp.name  AS backbone_name,
               bp.length AS backbone_length,
               count(*) AS n
          FROM constructs c
          LEFT JOIN backbone_proteins bp ON bp.id = c.backbone_id
         GROUP BY c.backbone_id, bp.name, bp.length
         ORDER BY n DESC
        """
    )


def used_peptide_ids(limit: int | None = None) -> list[int]:
    sql = "SELECT DISTINCT peptide_id FROM constructs ORDER BY peptide_id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [r["peptide_id"] for r in db.query(sql)]


def scores_of(row: dict[str, Any]) -> dict[str, Any]:
    """Stored JSONB may arrive already decoded (psycopg jsonb) or as text."""
    value = row.get("scores")
    if isinstance(value, str):
        return json.loads(value)
    return value or {}


def delivery_scores_of(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("delivery_scores")
    if isinstance(value, str):
        return json.loads(value)
    return value or {}
