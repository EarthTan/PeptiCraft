"""Scaffold view assembly."""
from __future__ import annotations

from typing import Any

from ..models.scaffold import (
    ScaffoldDetail,
    ScaffoldExperiment,
    ScaffoldSequence,
    ScaffoldSummary,
)
from ..repositories import scaffolds as repo

# Fields the frontend's BackboneProtein type declares and its pages render, but which the
# source dataset does not carry at all. Naming them explicitly lets the UI omit those blocks
# deliberately instead of drawing an empty card — which is what the audit found happening
# when `lab`, `characteristics`, `properties` and `expressionNotes` were declared, rendered,
# and never populated for any of the eight clusters.
UNAVAILABLE_FIELDS = (
    "lab",
    "common_name",
    "accession",
    "reference",
    "characteristics",
    "properties",
    "expression_notes",
)


def to_summary(row: dict[str, Any]) -> ScaffoldSummary:
    return ScaffoldSummary(
        id=row["id"],
        name=row["name"],
        short_name=row["short_name"],
        category=row.get("category"),
        applicant=row["applicant"],
        patent=row.get("patent_family"),
        length=row.get("length_aa"),
        species=row.get("species"),
        sequence_count=row.get("sequence_count") or 0,
        application_tags=list(row.get("application_tags") or []),
        route_ids=list(row.get("route_ids") or []),
        material_forms=list(row.get("material_forms") or []),
        max_evidence=row.get("max_evidence"),
        has_sequence=bool(row.get("aa_sequence")),
    )


def to_detail(row: dict[str, Any], sequences: list[dict[str, Any]],
              experiments: list[dict[str, Any]]) -> ScaffoldDetail:
    summary = to_summary(row)
    return ScaffoldDetail(
        **summary.model_dump(),
        description=row.get("description") or "",
        registrations=list(row.get("registrations") or []),
        registration_note=row.get("registration_note"),
        product_use=row.get("product_use"),
        potential_uses=row.get("potential_uses"),
        evidence_limits=row.get("evidence_limits"),
        patent_source_url=row.get("patent_source_url"),
        regulatory_evidence_url=row.get("regulatory_evidence_url"),
        sequences=[
            ScaffoldSequence(
                sequence_id=s["sequence_id"],
                fasta_filename=s.get("fasta_filename"),
                length=s["length_aa"],
                sequence=s["aa_sequence"],
                sha256=(s.get("sha256") or "").strip() or None,
                product_use=s.get("product_use"),
                regulatory_status=s.get("regulatory_status"),
                evidence_level=s.get("evidence_level"),
            )
            for s in sequences
        ],
        experiments=[
            ScaffoldExperiment(
                group=e.get("experiment_group"),
                level=e.get("experiment_level"),
                specific_experiments=e.get("specific_experiments"),
                principal_result=e.get("principal_result"),
                result_location=e.get("result_location"),
                evidence_limitations=e.get("evidence_limitations"),
            )
            for e in experiments
        ],
        unavailable_fields=list(UNAVAILABLE_FIELDS),
    )


def load_detail(scaffold_id: str) -> ScaffoldDetail | None:
    row = repo.get_scaffold(scaffold_id)
    if row is None:
        return None
    sequences = repo.sequences_for([scaffold_id]).get(scaffold_id, [])
    # The sequence table already carries the experiment columns, one row per patent
    # sequence, so the experiment view is a projection of the same rows rather than a
    # second query against a table this service does not own.
    return to_detail(row, sequences, sequences)


def list_summaries(route_id: str | None = None) -> list[ScaffoldSummary]:
    return [to_summary(r) for r in repo.list_scaffolds(route_id)]
