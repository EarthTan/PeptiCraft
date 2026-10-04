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
    "functional": "c.id",
}


def _where(
    direction: str | None,
    channel: str | None,
    status: str | None,
    min_rank: int | None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
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
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params


def list_constructs(
    *,
    direction: str | None = None,
    channel: str | None = None,
    status: str | None = None,
    min_rank: int | None = None,
    limit: int = 50,
    offset: int = 0,
    order: str = "rank",
) -> tuple[list[dict[str, Any]], int]:
    where, params = _where(direction, channel, status, min_rank)
    order_by = _ORDER.get(order, _ORDER["rank"])

    total = db.count(f"SELECT count(*) AS n FROM constructs c{where}", params)
    if total == 0:
        return [], 0

    rows = db.query(
        f"{_BASE_SELECT}{where} ORDER BY {order_by} LIMIT %s OFFSET %s",
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
