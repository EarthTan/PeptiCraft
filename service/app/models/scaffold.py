"""Scaffold models.

Grain note, because two different grains exist in the database and conflating them is the
easiest mistake to make here. `scaffold_patent_records` holds 27 rows at the *sequence
record* grain: 16 with a FASTA sequence plus 11 patent or product entries that have none.
The frontend works at the *protein cluster* grain: one row per construct, with the patent
sequence variants nested inside. `resouces/scaffold_database_2026-09-06/
scaffold_sequence_database.tsv` is the authoritative cluster-grain table — 16 rows
covering 8 clusters, 35 columns — and it is what `scaffold_library` is imported from. Columns
31-35, added after the first import, are the expression-system recommendation: host, vector
recorded, vector recommended, basis, source URL.

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


class ScaffoldExpression(BaseModel):
    """The expression system the source records for one sequence variant, and its basis.

    Values are verbatim from the sheet, Chinese included. That is not a translation gap:
    `无明确推荐` and `同家族公开路线；本行 1071 aa 对应关系待核实` are conclusions about how
    far the source's evidence goes, and paraphrasing them into English would widen a
    recommendation the source deliberately limited. The URLs beside them carry the evidence.

    The cluster row copies the representative variant's values — the longest sequence, which
    is what assembly uses — and reports that variant in `sequence_id`. The other variants
    each carry their own set.
    """

    system: str | None = Field(
        default=None,
        description="Recommended host and strain, with the source's qualifier when it has "
        "one (`E. coli BL21(DE3)`, `工程酵母（具体菌株未明确核实）`).",
    )
    vector_recorded: str | None = Field(
        default=None,
        description="The vector the patent or paper actually records. Not always the one "
        "recommended: two families record pET-32a and recommend it, one records pUC57 as a "
        "synthesis intermediate and does not.",
    )
    vector_recommended: str | None = Field(
        default=None,
        description="The vector the source recommends for this sequence. `无明确推荐` is a "
        "conclusion, not a missing value.",
    )
    rationale: str | None = Field(
        default=None,
        description="Why, and what the recommendation covers. Scope limits stay in the "
        "sentence — a tag left on the product, a host whose DE3 status is unconfirmed.",
    )
    source_url: str | None = None
    sequence_id: str | None = Field(
        default=None,
        description="The sequence record these values describe. On a cluster this is the "
        "representative variant, the one the assembly uses.",
    )


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
    expression: ScaffoldExpression | None = None


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
    expression: ScaffoldExpression | None = Field(
        default=None,
        description="Expression recommendation for the representative variant, which is the "
        "one a construct assembled on this cluster uses. Carried on the summary because that "
        "is the shape embedded in a construct response, and the Results page states the "
        "recommendation beside the assembly without a second request.",
    )
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
    unavailable_fields: list[str] = Field(default_factory=list)
