"""Read access to `scaffold_library` / `scaffold_library_sequences`.

Cluster grain. The application-tag arrays on each row are what connect a scaffold to an
application route, and they are the reason this table exists at all: the same information
is absent from `scaffold_patent_records`, `scaffold_groups` and `scaffold_experiments`.
"""
from __future__ import annotations

from typing import Any, Sequence

from .. import db

_SELECT = """
SELECT id, name, short_name, category, construct_cn, applicant, patent_family, species,
       length_aa, aa_sequence, sequence_count, application_tags, route_ids, material_forms,
       max_evidence, product_use, potential_uses, evidence_limits, registrations,
       registration_note, description, patent_source_url, regulatory_evidence_url,
       source_version
  FROM scaffold_library
"""

_ORDER = """
 ORDER BY CASE max_evidence
              WHEN 'E5' THEN 5 WHEN 'E4' THEN 4 WHEN 'E3' THEN 3
              WHEN 'E2' THEN 2 ELSE 1 END DESC,
          short_name
"""


def list_scaffolds(route_id: str | None = None) -> list[dict[str, Any]]:
    if route_id:
        return db.query(
            f"{_SELECT} WHERE route_ids @> ARRAY[%s]::text[]{_ORDER}", [route_id]
        )
    return db.query(f"{_SELECT}{_ORDER}")


def get_scaffold(scaffold_id: str) -> dict[str, Any] | None:
    return db.query_one(f"{_SELECT} WHERE id = %s", [scaffold_id])


def route_map() -> dict[str, list[str]]:
    """`{scaffold_id: [route_id, ...]}`.

    Derived from the scaffold side rather than read from the frontend's `routes.ts`, so the
    two directions of the relation cannot disagree. The frontend previously held both — a
    `scaffoldIds` array per route and a `routeIds` array per scaffold — with a comment
    warning that any change had to be made in both places.
    """
    rows = db.query("SELECT id, route_ids FROM scaffold_library ORDER BY id")
    return {r["id"]: list(r["route_ids"] or []) for r in rows}


def sequences_for(scaffold_ids: Sequence[str]) -> dict[str, list[dict[str, Any]]]:
    if not scaffold_ids:
        return {}
    rows = db.query(
        """
        SELECT sequence_id, scaffold_id, fasta_filename, length_aa, aa_sequence, sha256,
               product_use, regulatory_status, evidence_level, experiment_group,
               experiment_level, specific_experiments, principal_result, result_location,
               evidence_limitations
          FROM scaffold_library_sequences
         WHERE scaffold_id = ANY(%s)
         ORDER BY scaffold_id, length_aa DESC
        """,
        [list(scaffold_ids)],
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(row["scaffold_id"], []).append(row)
    return out


def sequence_by_id(sequence_id: str) -> dict[str, Any] | None:
    return db.query_one(
        "SELECT * FROM scaffold_library_sequences WHERE sequence_id = %s", [sequence_id]
    )


def available_sequences() -> dict[str, dict[str, Any]]:
    """`{sequence_id: {scaffold_id, length_aa, aa_sequence}}`, used when assembling a
    fused sequence. Only the columns the assembly needs are read: the full rows carry long
    evidence prose that would otherwise be pulled into memory for every construct."""
    rows = db.query(
        "SELECT sequence_id, scaffold_id, length_aa, aa_sequence FROM scaffold_library_sequences"
    )
    return {r["sequence_id"]: r for r in rows}
