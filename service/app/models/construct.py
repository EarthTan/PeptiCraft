"""Construct models — the shape the Library, Builder and Results pages read."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .common import BackboneBinding, Paginated, ScoreMeta, ScoreSemantics
from .linker import LinkerView
from .scaffold import ScaffoldSummary


class ConstructScores(BaseModel):
    """The nine scores the frontend renders.

    Every field is nullable on purpose. Roughly a fifth of the rows have no MHCflurry value
    at all, because that predictor only covers peptides of 5-15 aa. The old frontend
    supplied `0` for anything it did not have, which the tool table then read back as a
    genuine score of zero and paired with a FAIL badge. A null here means "not assessed",
    and `ScoreMeta.assessed` carries the same fact in boolean form so a caller does not have
    to distinguish null-means-missing from null-means-zero.
    """

    antioxidant: float | None = None
    toxicity: float | None = None
    hemolysis: float | None = None
    immunogenicity: float | None = None
    b_cell_epitope: float | None = None
    thermal_stability: float | None = None
    solubility: float | None = None
    cpp: float | None = None
    composite: float | None = None


class SupplementaryScores(BaseModel):
    """Real measurements that have no column in `ConstructScores` but are worth carrying.

    `immunogenicity_ii_pct_rank` is NetMHCIIpan's percent rank. It is 0-100 where lower is
    a stronger binder, so it is not a probability and must not be divided by 100 and
    presented as one. It covers the 326 rows the MHC-I predictor misses, which makes it the
    only immunogenicity signal for three of the four directions.
    """

    immunogenicity_ii_pct_rank: float | None = None
    allergenicity: float | None = None
    aggregation_a3v: float | None = None
    anoxpepred_frs: float | None = None
    anoxpepred_chel: float | None = None
    aopxsvm: float | None = None
    amp_esm: float | None = None
    imfp_lg_amp: float | None = None
    imfp_lg_aip: float | None = None
    tipred: float | None = None


class SequenceSegment(BaseModel):
    """One coloured block in the sequence viewer."""

    label: str
    sequence: str
    color: str
    type: str = Field(description="`backbone`, `linker` or `peptide`.")
    available: bool = Field(
        default=True,
        description="False when the part exists in the assembly but its sequence is not "
        "known. The scaffold segment is unavailable for every row whose binding is a "
        "placeholder, and the UI should show the label without colouring residues.",
    )


class PeptideInfo(BaseModel):
    id: int
    sequence: str
    length: int
    source: str
    source_version: str
    source_accession: str | None = None
    seq_md5: str


class DeliveryAdjustedScores(BaseModel):
    """Scores recomputed under one application route's weighting profile.

    The key set matches `DeliveryRoute.id`. `immunogenicity` is a property of the peptide
    and does not move with the route, so it repeats unchanged in every entry; the other
    three depend on the route's weight tiers and the composite is recomputed from them.
    """

    cpp: float | None = None
    solubility: float | None = None
    thermal_stability: float | None = None
    immunogenicity: float | None = None
    composite: float | None = None
    components: dict[str, float] = Field(
        default_factory=dict,
        description="The normalised, direction-corrected components and the weight each "
        "was given. Exposed so a composite can be reproduced by hand from one response.",
    )
    weights: dict[str, float] = Field(default_factory=dict)


class SafetyGate(BaseModel):
    """One veto check, evaluated against a named threshold."""

    key: str
    label: str
    tool: str
    value: float | None = None
    threshold: float
    threshold_source: str
    passed: bool | None = Field(
        default=None,
        description="None when the metric was not assessed. An unassessed metric does not "
        "eliminate a candidate: the pipeline's null-passthrough rule, stated in all four "
        "direction proposals, is that a score eliminates only when it is present and out "
        "of bounds.",
    )
    borderline: bool = False
    is_veto_gate: bool = Field(
        default=False,
        description="Whether a failure on this gate eliminates the candidate. Carried here "
        "rather than left to the caller to infer from the key, so the set of veto gates is "
        "declared once in the service instead of being restated in the analysis template and "
        "again in the interface.",
    )
    higher_is_better: bool = Field(
        default=False,
        description="Which side of the threshold is the failing side. Every gate but the "
        "MHC-II percent rank fails on a high value, and the rank fails on a low one because a "
        "low percent rank means a stronger binder. A reader that says 'above the limit' "
        "without checking this states the opposite for the rank.",
    )
    note: str | None = None


class SafetyVerdict(BaseModel):
    route_id: str | None
    immunogenicity_threshold: float | None
    verdict: str = Field(
        description="`clear` all assessed gates passed; `vetoed` at least one failed; "
        "`borderline` no gate failed but at least one sits within 10% of its threshold; "
        "`indeterminate` no gate was assessed at all."
    )
    gates: list[SafetyGate]
    unassessed: list[str] = Field(
        default_factory=list,
        description="Gate keys with no measured value. The Results page renders these as "
        "`Not assessed` rather than as a pass.",
    )
    vetoed_by: list[str] = Field(default_factory=list)


class ConstructSummary(BaseModel):
    """List-row shape. Carries enough to render a card without a second request."""

    id: str
    name: str
    direction: str
    channel: str
    status: str
    rank: int | None = None
    direction_label: str
    peptide_sequence: str
    peptide_length: int
    backbone_name: str | None = None
    backbone_id: str | None = None
    linker_name: str | None = None
    functional_score: float | None = None
    functional_score_key: str = Field(
        description="The `peptide_enrichment.tool` key the value was read from, verbatim. It "
        "is an identifier, not a label: the four directions read from `anoxpepred-frs`, "
        "`amp-esm`, `imfp_lg_AIP` and `tipred`, which do not share a spelling convention "
        "because they are the keys the pipeline wrote.",
    )
    functional_score_label: str = Field(
        default="",
        description="The predictor's name for display, so the interface never prints a "
        "database key. Comes from the same table the detail page's score grid uses.",
    )
    semantics: ScoreSemantics = Field(
        default=ScoreSemantics.probability,
        description="How the functional score may be read. It is on the list row, not only on "
        "the detail, because two of the four directions rank by a model that separates "
        "'looks like a functional peptide' from 'is one'. A card that prints that number "
        "beside a probability without this flag presents a ranking position as a "
        "confidence.",
    )
    composite: float | None = None
    safety_verdict: str | None = None
    backbone_binding: BackboneBinding = Field(
        default=BackboneBinding.placeholder,
        description="Present on the list row as well as the detail, because a card that shows "
        "a scaffold name without this qualifier would read as a verified choice. `verified` "
        "means the construct's stored backbone row carries a real sequence; `placeholder` "
        "means it holds a marker string and no fused sequence can be emitted; `inferred` "
        "means the scaffold was named in the request, not read from the construct.",
    )


class ConstructDetail(ConstructSummary):
    """Full shape for the Results page."""

    backbone_binding_note: str
    scaffold: ScaffoldSummary | None = None
    linker: LinkerView | None = None
    linker_note: str = Field(
        default="",
        description="Where the linker the fused sequence was built with came from. Read "
        "alongside `backbone_binding_note`: an assembly can take its scaffold from the "
        "record and its linker from the request, or the other way round, so the two "
        "provenance accounts are reported separately rather than merged into one.",
    )
    peptide: PeptideInfo
    full_sequence: str | None = Field(
        default=None,
        description="The fused sequence, assembled as backbone + linker + peptide. Null "
        "while the scaffold sequence is unknown, because emitting a two-part string under "
        "a field named `full_sequence` is what the placeholder rows did and it reads as a "
        "real construct sequence. Present when the stored binding is `verified` and the "
        "bound backbone row carries a real sequence, or when the request named a scaffold.",
    )
    assembled_sequence_available: bool
    segments: list[SequenceSegment]
    scores: ConstructScores
    supplementary: SupplementaryScores
    score_meta: dict[str, ScoreMeta]
    delivery_scores: dict[str, DeliveryAdjustedScores]
    safety: SafetyVerdict
    unassessed_metrics: list[str]
    assessed_flags: dict[str, bool]


class ConstructPage(Paginated[ConstructSummary]):
    pass
