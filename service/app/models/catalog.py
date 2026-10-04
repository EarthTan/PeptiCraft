"""Reference data: function directions, application routes, pipeline rounds, tool metadata.

These four groups replace the frontend's `directions.ts`, `routes.ts`, `pipeline.ts` and
`analysis.ts`. They are served rather than hardcoded because each one carries a number that
has to agree with the database: the direction counts, the immunogenicity gate a safety
verdict is taken against, and the threshold a score is judged by. The frontend previously
held all four in separate copies and they had drifted — `SAFETY_THRESHOLDS` appeared twice,
the direction counts disagreed with the table, and the antioxidant acceptance floor of 0.70
was quoted in generated prose while `toolMetadata` had no threshold field for it at all.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .common import BarrierTier, EvidenceLevel, MaterialForm, WeightTier


class DirectionCounts(BaseModel):
    """Counts read from `constructs`, not from a hand-written constant."""

    total: int
    top: int
    bottom: int
    by_status: dict[str, int] = Field(
        default_factory=dict,
        description="`passed` / `failed_safety` / `failed_score` / `WIP`.",
    )


class FunctionDirection(BaseModel):
    id: str
    name: str
    icon: str
    color: str
    description: str
    precursor_count: int = Field(
        description="Peptides actually scored by this direction's functional predictor."
    )
    construct_count: int
    status: str = Field(
        description="`ready` when the direction has ranked constructs whose status is "
        "`passed`; `wip` when the direction has constructs but they are still marked WIP. "
        "A direction with no constructs is `empty` and must not be offered as a filter."
    )
    counts: DirectionCounts


class RouteScreening(BaseModel):
    """How a route shifts the score weights and the safety gate.

    This is a platform convention rather than something the dataset supplies: the dataset
    states which routes exist, it says nothing about thresholds. The three weight tiers
    keep the platform's multiplier convention (high 1.8 / medium 1.0 / low 0.4).
    """

    cpp_weight: WeightTier
    solubility_weight: WeightTier
    thermal_stability_weight: WeightTier
    immunogenicity_threshold: float = Field(ge=0.0, le=1.0)
    threshold_note: str
    extra_gates: list[str] = Field(default_factory=list)


class DeliveryRoute(BaseModel):
    """One application route — the single choice made in Step 1 of the Builder.

    A route carries two responsibilities: it narrows the scaffold pool, and it sets the
    screening profile. The earlier four-layer structure (primary scenario, secondary
    scenario, primary delivery, secondary delivery) is retired.
    """

    id: str
    name: str
    icon: str
    application_tag: str = Field(
        description="The tag as written in the scaffold dataset's application columns, "
        "kept for traceability back to the source table."
    )
    contact_interface: str
    barrier_tier: BarrierTier
    barrier_label: str
    immune_exposure: str
    screening: RouteScreening
    application_techniques: list[str] = Field(default_factory=list)
    scaffold_ids: list[str] = Field(default_factory=list)
    emerging: bool = False
    emerging_note: str | None = None


class PipelineStage(BaseModel):
    round: int
    name: str
    input: str
    output: str
    duration: str
    tools: list[str]
    description: str


class PipelineView(BaseModel):
    """Rounds 1-4 are what the platform carries.

    Rounds 5-8 depend on 3D structure prediction, which the MVP excludes, and the two
    `composite` definitions in the old frontend collided precisely here: Round 3 defines a
    composite as a Winsorized standard-deviation weighting of four metrics, Round 7 defines
    a different composite as 40% SASA + 40% (1 - Aggrescan3D) + 20% pLDDT. Only the first
    is implementable without structures, so `composite_definition` below states which one
    the platform's scores use and `excluded` records why the other is out.
    """

    included: list[PipelineStage]
    excluded: list[PipelineStage]
    composite_definition: str
    excluded_note: str


class ToolDefinition(BaseModel):
    """One predictor behind one score."""

    key: str
    tool: str
    measures: str
    higher_is_better: bool
    group: str
    semantics: str
    threshold: float | None = None
    threshold_source: str | None = None
    threshold_note: str | None = None
    coverage_note: str | None = None
    is_veto_gate: bool = False


class ScaffoldCategoryView(BaseModel):
    id: str
    label: str
    scaffold_ids: list[str]


class MaterialFormOption(BaseModel):
    id: MaterialForm
    label: str


class ReferenceData(BaseModel):
    """Everything the frontend needs that is not a construct, scaffold or linker."""

    directions: list[FunctionDirection]
    routes: list[DeliveryRoute]
    tools: list[ToolDefinition]
    evidence_levels: list[dict[str, str]]
    material_forms: list[MaterialFormOption]
    categories: list[ScaffoldCategoryView]
