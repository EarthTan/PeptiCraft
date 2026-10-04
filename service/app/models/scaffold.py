"""Scaffold models.

Grain note, because two different grains exist in the database and conflating them is the
easiest mistake to make here. `scaffold_patent_records` holds 27 rows at the *sequence
record* grain: 16 with a FASTA sequence plus 11 patent or product entries that have none.
The frontend works at the *protein cluster* grain: one row per construct, with the patent
sequence variants nested inside. `data/scaffold_database_2026-09-06/
scaffold_sequence_database.tsv` is the authoritative cluster-grain table — 16 rows
covering 8 clusters, 30 columns — and it is what `scaffold_library` is imported from.

The cluster's application tags are what connect a scaffold to an application route. They
are the five columns `Topical appliance`, `Mask patch`, `Hair care`, `Wound dressing` and
`Injectable filler`, each holding `Yes` or blank, and they are the only place in the
dataset that states which routes exist. Narrowing the pool by `route_ids` yields 2 / 4 / 2
/ 4 / 2 scaffolds in that column order. The frontend holds no copy of either direction:
`routes.ts` was deleted with the rest of the mock data layer, and `route_ids` on this table
is now the single source for the relation.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .common import EvidenceLevel, MaterialForm


class ScaffoldSequence(BaseModel):
    """One patent sequence variant inside a cluster."""

    sequence_id: str
    fasta_filename: str | None = None
    length: int
    sequence: str
    sha256: str | None = None
    product_use: str | None = None
    regulatory_status: str | None = None
    evidence_level: EvidenceLevel | None = None


class ScaffoldExperiment(BaseModel):
    group: str | None = None
    level: str | None = None
    specific_experiments: str | None = None
    principal_result: str | None = None
    result_location: str | None = None
    evidence_limitations: str | None = None


class ScaffoldSummary(BaseModel):
    """Card shape, and the shape embedded inside a construct response."""

    id: str
    name: str
    short_name: str
    category: str | None = None
    applicant: str
    patent: str | None = None
    length: int | None = None
    species: str | None = None
    sequence_count: int = 0
    application_tags: list[str] = Field(default_factory=list)
    route_ids: list[str] = Field(default_factory=list)
    material_forms: list[MaterialForm] = Field(default_factory=list)
    max_evidence: EvidenceLevel | None = None
    has_sequence: bool = Field(
        description="False for scaffold clusters whose sequences the source table does not "
        "carry. Such a cluster cannot contribute a backbone segment to a fused sequence."
    )


class ScaffoldDetail(ScaffoldSummary):
    description: str
    registrations: list[str] = Field(default_factory=list)
    registration_note: str | None = None
    product_use: str | None = None
    potential_uses: str | None = None
    evidence_limits: str | None = None
    patent_source_url: str | None = None
    regulatory_evidence_url: str | None = None
    sequences: list[ScaffoldSequence] = Field(default_factory=list)
    experiments: list[ScaffoldExperiment] = Field(default_factory=list)

    # Declared by the frontend type and rendered by the UI, but not present in the source
    # dataset at all. They are carried as explicit nulls with `unavailable_fields` naming
    # them, so the UI can omit those blocks knowingly instead of rendering an empty card and
    # leaving the reader to guess whether the value is missing or the field is broken.
    lab: str | None = None
    common_name: str | None = None
    accession: str | None = None
    reference: str | None = None
    characteristics: list[str] | None = None
    properties: list[dict[str, str]] | None = None
    expression_notes: str | None = None
    unavailable_fields: list[str] = Field(default_factory=list)
