"""Shared value objects.

The field names here are the contract the frontend reads, and they are written out by hand in
`app/src/api/types.ts`. The two are compared by reading both rather than by generating one from
the other: the frontend has no generated client, and a generator would add a build step to a
service whose whole value is that it is easy to read.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class EvidenceLevel(StrEnum):
    """Highest verifiable evidence tier, from the dataset's grading sheet.

    E1 purified protein / cell-free work, E2 cell work, E3 animal work, E4 human use or
    controlled clinical study, E5 regulatory review and post-market safety data. The label
    records the highest tier that could be verified; it does not mean every experiment
    below or above that tier was carried out.
    """

    E1 = "E1"
    E2 = "E2"
    E3 = "E3"
    E4 = "E4"
    E5 = "E5"


class BarrierTier(StrEnum):
    """Delivery routes grouped by the interface the construct contacts.

    `tissue` goes into tissue, `breached` contacts an open wound bed, `intact` stays
    outside the stratum corneum, `non-living` contacts a keratinised hair shaft. This axis
    sets the magnitude of immune exposure and is why two of the five routes tighten the
    immunogenicity gate.
    """

    tissue = "tissue"
    breached = "breached"
    intact = "intact"
    non_living = "non-living"


class MaterialForm(StrEnum):
    """A property of the scaffold, not a user-facing choice.

    The dataset has no such column. These values were extracted from the prose in the
    product/use, potential-applications and key-results columns and still need the team's
    confirmation.
    """

    lyophilized = "lyophilized"
    self_assembled_hydrogel = "self-assembled-hydrogel"
    injectable_gel = "injectable-gel"
    film = "film"
    fiber = "fiber"
    sheet = "sheet"
    solution = "solution"


class WeightTier(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class ScoreSemantics(StrEnum):
    """How a functional score may be read.

    `probability` may be presented as a probability. `ranking_only` may be used for
    ordering but must never be shown as a probability or a confidence: the anti-inflammatory
    records carry `func_score_meaning = "ranking_only_not_probability"` in their stored
    scores, and the direction proposal documents that the three AIP models behind that
    number separate "looks like a functional peptide" from "is anti-inflammatory", which
    makes it a ranking signal rather than a calibrated probability.

    `class_label` covers tools whose stored value is a class index rather than a score,
    such as AOPxSVM, whose stored value is 1 and whose probability lives in `details.prob`.
    """

    probability = "probability"
    ranking_only = "ranking_only"
    class_label = "class_label"


class BackboneBinding(StrEnum):
    """Where a construct's scaffold came from.

    Every one of the 496 rows in `constructs` points at `backbone_proteins.id = 1`, which
    holds the placeholder string `PLACEHOLDER_4RepCT` with length 0. The assembly script
    says so explicitly: it persisted a minimal peptide x placeholder-backbone x
    placeholder-linker combination so the schema and sample data would be complete, and
    left the real scaffold binding to "the frontend plus a backend construct-calculation
    service".

    `verified` means the binding came from the pipeline and the scaffold has a real
    sequence. `placeholder` means the stored binding is a stand-in and any fused sequence
    shown is incomplete. `inferred` means this service assigned a scaffold from the real
    library on its own, which is traceable but is not a pipeline result.

    The service decides between the first two by reading the row `backbone_id` resolves to:
    a real sequence means `verified`, a marker string or an empty sequence means
    `placeholder`. It does not assume every row is a placeholder — a construct whose binding
    was set properly assembles into a full sequence and is reported as `verified`.
    """

    verified = "verified"
    placeholder = "placeholder"
    inferred = "inferred"


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class AppliedThreshold(BaseModel):
    """A gate threshold together with where it came from."""

    value: float
    source: str = Field(
        description="`tool` when the threshold ships with the predictor's own details, "
        "`route` when it comes from the application route's screening profile, "
        "`project` when it is a platform-wide constant."
    )
    note: str | None = None


class ScoreMeta(BaseModel):
    """Everything needed to render one score cell honestly."""

    key: str
    tool: str
    measures: str
    higher_is_better: bool
    group: str = Field(description="`function`, `safety` or `developability`.")
    assessed: bool
    semantics: ScoreSemantics = ScoreSemantics.probability
    applied_threshold: AppliedThreshold | None = None
    is_veto_gate: bool = Field(
        default=False,
        description="True only for toxicity, haemolysis and immunogenicity. B-cell "
        "epitope and allergenicity are soft signals and are not veto gates, which is why "
        "the frontend's tool grouping must not label the whole safety group as veto.",
    )
