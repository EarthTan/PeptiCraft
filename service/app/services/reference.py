"""Reference data: the single source of truth for thresholds, weights and route profiles.

Everything here used to live in the frontend, spread across four modules and duplicated in
places. Consolidating it is not tidiness for its own sake — three of the defects the
2026-09-17 audit found were caused by copies drifting apart:

  * `SAFETY_THRESHOLDS` was written twice, once in the Library page and once in the Results
    page, with a comment claiming the two shared a definition.
  * The immunogenicity gate was applied globally at 0.50 while the route definitions
    specified 0.35 / 0.50 / 0.60, so a construct sitting on the tightened boundary was shown
    as clearing every gate.
  * The generated prose cited a 0.70 acceptance floor for AnOxPePred while the tool metadata
    carried no threshold for it at all, leaving the reader unable to find the number.

Threshold values below are read from each tool's own `details` JSON in `peptide_enrichment`
rather than restated from documentation, and they match what the rows carry:
`toxinpred3` 0.38, `hemopi2` 0.55, `bepipred3` 0.1512, `plm4cpps` 0.15, `algpred2` 0.3,
`anoxpepred-frs` 0.5, `tipred` 0.5, `imfp_lg_*` 0.5.
"""
from __future__ import annotations

from typing import Any

from ..models.catalog import (
    DeliveryRoute,
    FunctionDirection,
    MaterialFormOption,
    PipelineStage,
    PipelineView,
    RouteScreening,
    ScaffoldCategoryView,
    ToolDefinition,
)
from ..models.common import BarrierTier, MaterialForm, WeightTier

# ---------------------------------------------------------------------------
# Application routes
# ---------------------------------------------------------------------------
#
# Five routes, one per application tag in the scaffold dataset. Each carries two
# responsibilities: narrowing the scaffold pool, and setting the screening profile.
#
# The weight tiers and immunogenicity gates are a platform convention — the dataset states
# which routes exist, it says nothing about thresholds. The three tiers keep the platform's
# multiplier convention (high 1.8 / medium 1.0 / low 0.4).
#
# Wound dressing is the one route whose gate was changed from the original topical value.
# The dataset describes its contact interface as an open wound bed, so the barrier is
# already breached and the construct meets tissue fluid directly. That puts immune exposure
# in the same band as injection rather than in the intact-skin band, and the gate is
# tightened from 0.50 to 0.35 accordingly.

ROUTES: list[DeliveryRoute] = [
    DeliveryRoute(
        id="wound-dressing",
        name="Wound Dressing",
        icon="bandage",
        application_tag="Wound dressing",
        contact_interface=(
            "Applied to an open wound, contacting the wound bed and tissue fluid directly"
        ),
        barrier_tier=BarrierTier.breached,
        barrier_label="Breached barrier",
        immune_exposure=(
            "High — the skin barrier is already broken, so the construct contacts tissue "
            "fluid directly"
        ),
        screening=RouteScreening(
            cpp_weight=WeightTier.low,
            solubility_weight=WeightTier.medium,
            thermal_stability_weight=WeightTier.medium,
            immunogenicity_threshold=0.35,
            threshold_note=(
                "The barrier is breached and the construct contacts tissue fluid directly, "
                "so immune exposure is in the same band as injection. The gate is tightened "
                "to 0.35 rather than treated as intact skin."
            ),
            extra_gates=["Sterility", "Biocompatibility", "Endotoxin control"],
        ),
        application_techniques=["Direct application to the wound bed", "Carried on a dressing"],
    ),
    DeliveryRoute(
        id="mask-patch",
        name="Mask / Patch",
        icon="shapes",
        application_tag="Mask patch",
        contact_interface="Applied to the face or a local skin area under occlusion",
        barrier_tier=BarrierTier.intact,
        barrier_label="Intact barrier",
        immune_exposure=(
            "Moderate — the barrier is intact, but occlusion raises stratum corneum "
            "permeability, which lifts both penetration and sensitisation risk"
        ),
        screening=RouteScreening(
            cpp_weight=WeightTier.medium,
            solubility_weight=WeightTier.high,
            thermal_stability_weight=WeightTier.medium,
            immunogenicity_threshold=0.50,
            threshold_note=(
                "Intact barrier, but occlusion enhances penetration, so immune exposure "
                "sits slightly above an unoccluded topical. Standard gate of 0.50."
            ),
            extra_gates=["Irritation and sensitisation under occlusion"],
        ),
        application_techniques=["Manual application", "Hydrogel patch"],
    ),
    DeliveryRoute(
        id="injectable-filler",
        name="Injectable Filler",
        icon="syringe",
        application_tag="Injectable filler",
        contact_interface="Delivered into the dermis or subcutaneous tissue through a needle",
        barrier_tier=BarrierTier.tissue,
        barrier_label="Into tissue",
        immune_exposure=(
            "Highest — the barrier is bypassed entirely and the construct enters the tissue; "
            "the only one of the five routes that goes into the body"
        ),
        screening=RouteScreening(
            cpp_weight=WeightTier.low,
            solubility_weight=WeightTier.medium,
            thermal_stability_weight=WeightTier.medium,
            immunogenicity_threshold=0.35,
            threshold_note=(
                "The construct enters the tissue, where the immune system can recognise it "
                "directly. Screened against the strictest gate, 0.35."
            ),
            extra_gates=[
                "Sterility",
                "Endotoxin control",
                "Injectability / rheology",
                "In vivo safety",
            ],
        ),
        application_techniques=["Conventional needle injection"],
    ),
    DeliveryRoute(
        id="topical-film",
        name="Topical Film",
        icon="droplets",
        application_tag="Topical appliance",
        contact_interface=(
            "Spread on the skin surface, drying down to or retaining a protein film, "
            "with no occlusion"
        ),
        barrier_tier=BarrierTier.intact,
        barrier_label="Intact barrier",
        immune_exposure=(
            "Low — the barrier is intact and there is no occlusion, so the construct stays "
            "largely outside the stratum corneum"
        ),
        screening=RouteScreening(
            cpp_weight=WeightTier.high,
            solubility_weight=WeightTier.high,
            thermal_stability_weight=WeightTier.low,
            immunogenicity_threshold=0.50,
            threshold_note=(
                "Intact barrier with no occlusion, so immune exposure is low. With neither a "
                "needle nor occlusion-driven penetration, membrane penetration becomes the "
                "main bottleneck. Applied at room temperature, so the thermal stability "
                "requirement is the lowest of the five."
            ),
            extra_gates=["Film formation", "Spreadability"],
        ),
        application_techniques=["Manual spreading", "Spray"],
    ),
    DeliveryRoute(
        id="hair-coating",
        name="Hair Care",
        icon="waves",
        application_tag="Hair care",
        contact_interface=(
            "Coated onto the hair shaft, contacting tissue that is already keratinised and dead"
        ),
        barrier_tier=BarrierTier.non_living,
        barrier_label="Non-living surface",
        immune_exposure=(
            "Lowest — the hair shaft has no blood vessels, lymphatics or immune cells, so the "
            "construct never enters the body"
        ),
        screening=RouteScreening(
            cpp_weight=WeightTier.low,
            solubility_weight=WeightTier.high,
            thermal_stability_weight=WeightTier.medium,
            immunogenicity_threshold=0.60,
            threshold_note=(
                "The hair shaft is keratinised dead tissue and the construct never reaches "
                "the immune system, so the gate is the widest of the five."
            ),
            extra_gates=[
                "Adhesion to the hair shaft",
                "Wash resistance",
                "No adverse effect on hair feel",
            ],
        ),
        application_techniques=[
            "Shampoo / conditioner formulation",
            "Spray",
            "Hair shaft coating",
        ],
        emerging=True,
        emerging_note=(
            "The evidence behind this route is still accumulating. On the surface it carries "
            "two established companies, but Trautec's E5 evidence comes from its wound-dressing "
            "product (Kefuyan, Jiangsu provincial registration no. 20232141168, registered for "
            "wound care rather than hair care); hair care appears only as a proposal in the "
            "patent. AMSilk's eADF4(C16) reaches only E1, with the dataset stating its evidence "
            "is mainly cell-free and ex vivo. No human or regulatory evidence tied to this "
            "indication exists."
        ),
    ),
]

ROUTES_BY_ID = {r.id: r for r in ROUTES}

# high 1.8 / medium 1.0 / low 0.4
WEIGHT_MULTIPLIER = {"high": 1.8, "medium": 1.0, "low": 0.4}

# ---------------------------------------------------------------------------
# Tool metadata
# ---------------------------------------------------------------------------
#
# Nine scores, eight predictors plus the composite. `is_veto_gate` is true for exactly
# three of them. The audit flagged that the frontend's safety group was labelled
# "Safety (veto gates)" while containing BepiPred-3.0, which is not a veto — the pipeline's
# Round 2 states three veto checks, and `anyVeto` in the analysis module also counted only
# three. The flag is explicit here so a grouping cannot imply otherwise.

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        key="antioxidant",
        tool="AnOxPePred (FRS head)",
        measures=(
            "Probability that the peptide scavenges free radicals. The predictor emits a "
            "separate chelating head; the free-radical-scavenging head is what ranks the "
            "antioxidant direction."
        ),
        higher_is_better=True,
        group="function",
        semantics="probability",
        threshold=0.5,
        threshold_source="tool",
        threshold_note="The predictor's own activity boundary is 0.5 on the FRS head.",
        coverage_note="All 496 constructs carry a value.",
    ),
    ToolDefinition(
        key="toxicity",
        tool="ToxinPred3",
        measures="Predicted toxicity of the peptide.",
        higher_is_better=False,
        group="safety",
        semantics="probability",
        threshold=0.38,
        threshold_source="tool",
        threshold_note=(
            "Calibrated on the project's own 20.20 M-peptide library rather than taken from "
            "the model's default, so the boundary is a project choice written into the "
            "predictor's own details."
        ),
        coverage_note="All 496 constructs carry a value.",
        is_veto_gate=True,
    ),
    ToolDefinition(
        key="hemolysis",
        tool="HemoPI2",
        measures="Predicted haemolytic activity — lysis of red blood cells.",
        higher_is_better=False,
        group="safety",
        semantics="probability",
        threshold=0.55,
        threshold_source="tool",
        coverage_note=(
            "All 496 constructs carry a value here. Across the wider 20.2 M library the "
            "predictor only covers a 500,000-peptide sample."
        ),
        is_veto_gate=True,
    ),
    ToolDefinition(
        key="immunogenicity",
        tool="MHCflurry 2.0",
        measures=(
            "MHC class I presentation score, used as a proxy for T-cell immunogenicity. A "
            "higher score means a stronger predicted binder and therefore greater risk."
        ),
        higher_is_better=False,
        group="safety",
        semantics="probability",
        threshold=None,
        threshold_source="route",
        threshold_note=(
            "The gate is per route — 0.35 for wound dressing and injectable filler, 0.50 for "
            "mask/patch and topical film, 0.60 for hair care — and is applied from the route's "
            "screening profile rather than from a global constant. For reference, the "
            "predictor's own Strong Binder boundary sits at about 0.50, so the two tightened "
            "routes are stricter than the model's default and the hair-care route is looser."
        ),
        coverage_note=(
            "Only 117 of the 496 constructs carry an MHC-I value, because the predictor covers "
            "peptides of 5-15 aa. The remaining rows are reported as not assessed rather than "
            "as passing; a separate MHC-II percent rank covers 326 of them."
        ),
        is_veto_gate=True,
    ),
    ToolDefinition(
        key="b_cell_epitope",
        tool="BepiPred-3.0",
        measures=(
            "B-cell epitope propensity — how likely the peptide is to be recognised by "
            "antibodies."
        ),
        higher_is_better=False,
        group="safety",
        semantics="probability",
        threshold=0.1512,
        threshold_source="tool",
        coverage_note="All 496 constructs carry a value in the enrichment table.",
        is_veto_gate=False,
    ),
    ToolDefinition(
        key="thermal_stability",
        tool="TemStaPro",
        measures=(
            "Predicted thermal stability, reported as the probability that the peptide "
            "tolerates its assigned temperature band. Relevant to fabrication, storage and "
            "shelf life."
        ),
        higher_is_better=True,
        group="developability",
        semantics="probability",
        threshold=None,
        threshold_note=(
            "The predictor is multi-class over temperature bands rather than binary, so it "
            "carries no single acceptance boundary. The band assignment travels in the row's "
            "label beside the score."
        ),
        coverage_note="All 496 constructs carry a value.",
    ),
    ToolDefinition(
        key="solubility",
        tool="SoDoPE",
        measures="Predicted solubility on recombinant expression — drives purification yield.",
        higher_is_better=True,
        group="developability",
        semantics="probability",
        threshold=None,
        coverage_note="All 496 constructs carry a value.",
    ),
    ToolDefinition(
        key="cpp",
        tool="pLM4CPPs",
        measures=(
            "Cell-penetrating propensity. Load-bearing for the topical routes, where membrane "
            "penetration — not injection — is the barrier to entry."
        ),
        higher_is_better=True,
        group="developability",
        semantics="probability",
        threshold=0.15,
        threshold_source="tool",
        coverage_note="All 496 constructs carry a value.",
    ),
    ToolDefinition(
        key="composite",
        tool="Composite scorer",
        measures=(
            "A derived ranking score, not a prediction. Weighted combination of the "
            "developability components under one application route's weighting profile."
        ),
        higher_is_better=True,
        group="developability",
        semantics="ranking_only",
        threshold_note=(
            "Computed by this service per route; the weights and the components are returned "
            "alongside the value so it can be reproduced from a single response."
        ),
    ),
]

TOOLS_BY_KEY = {t.key: t for t in TOOLS}

# Supplementary measurements that are real but have no column in the nine-score contract.
# Spelled as the field names in `SupplementaryScores`, for the same reason `TOOLS` is.
SUPPLEMENTARY_TOOL_KEYS = (
    "immunogenicity_ii_pct_rank",
    "allergenicity",
    "aggregation_a3v",
)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

PIPELINE_INCLUDED: list[PipelineStage] = [
    PipelineStage(
        round=1,
        name="Functional sorting",
        input="~20.2 M peptides",
        output="Ranked candidate pool",
        duration="~30 min",
        tools=["AnOxPePred", "iMFP-LG", "TIPred", "AMPlify"],
        description=(
            "One functional predictor per direction ranks the full peptide library. Which "
            "predictor is used depends on the direction: the antioxidant direction is ranked "
            "by AnOxPePred's free-radical-scavenging head, antimicrobial by iMFP-LG's AMP "
            "channel, anti-melanin by TIPred, and anti-inflammatory by iMFP-LG's AIP channel."
        ),
    ),
    PipelineStage(
        round=2,
        name="Safety hard-threshold screening",
        input="Ranked candidate pool",
        output="Peptides passing all assessed veto gates",
        duration="~24 h",
        tools=["ToxinPred3", "HemoPI2", "MHCflurry"],
        description=(
            "Three veto checks, applied with the pipeline's null-passthrough rule: a metric "
            "eliminates a candidate only when it is present and out of bounds, and an "
            "unassessed metric does not eliminate anything. Toxicity below 0.38 (ToxinPred3), "
            "haemolysis below 0.55 (HemoPI2), and MHC-I presentation under the route's own "
            "gate (MHCflurry). There is no weighted compensation — a single failure removes "
            "the candidate. This round is the pipeline bottleneck: ToxinPred3 inference is "
            "single-threaded and takes roughly a day."
        ),
    ),
    PipelineStage(
        round=3,
        name="Developability scoring",
        input="Safety-passing peptides",
        output="~700 ranked peptides",
        duration="~5 h",
        tools=["BepiPred-3.0", "TemStaPro", "SoDoPE", "pLM4CPPs"],
        description=(
            "Four developability signals combined into a composite by a Winsorized "
            "standard-deviation weighting: components with high spread — genuinely "
            "discriminative within the candidate pool — are up-weighted, and flat components "
            "are down-weighted automatically. No manual weight preset is involved, which is "
            "why the weights differ between directions."
        ),
    ),
    PipelineStage(
        round=4,
        name="Enumeration and assembly",
        input="Ranked peptides",
        output="Pre-computed constructs",
        duration="~30 min",
        tools=["Construct Builder"],
        description=(
            "Ranked peptides are fused onto scaffolds with a linker to produce complete "
            "construct sequences. The platform currently carries 496 constructs across four "
            "directions; the binding between a construct and a real scaffold is still a "
            "placeholder pending assembly against the scaffold library."
        ),
    ),
]

PIPELINE_EXCLUDED: list[PipelineStage] = [
    PipelineStage(
        round=5,
        name="3D folding prediction",
        input="Constructs",
        output="Structure files",
        duration="~6 h",
        tools=["OmegaFold"],
        description=(
            "Predicts 3D structures. Excluded from the MVP: computationally heavy, and silk "
            "GGX-repeat sequences yield inherently low confidence (around 0.42 pLDDT) under "
            "these methods, so the output would not support a decision."
        ),
    ),
    PipelineStage(
        round=6,
        name="Structure evaluation",
        input="Structure files",
        output="Scored structures",
        duration="~5 min",
        tools=["FreeSASA", "Aggrescan3D"],
        description=(
            "Solvent-accessible surface area and 3D aggregation propensity from predicted "
            "structures. Excluded with Round 5, on which it depends."
        ),
    ),
    PipelineStage(
        round=7,
        name="Structure-based ranking",
        input="Scored structures",
        output="Ranked structures",
        duration="Instant",
        tools=["Composite scorer"],
        description=(
            "The second of the two definitions of a composite score in the old frontend: "
            "40% SASA + 40% (1 - Aggrescan3D) + 20% pLDDT. Excluded with Rounds 5 and 6. The "
            "composite the platform reports is not this one."
        ),
    ),
    PipelineStage(
        round=8,
        name="AlphaFold3 validation",
        input="Selected constructs",
        output="High-accuracy structure files",
        duration="~22.5 h",
        tools=["AlphaFold3"],
        description=(
            "Optional high-accuracy structural validation of a small number of constructs. "
            "Excluded from the MVP with the rest of the structure track."
        ),
    ),
]

PIPELINE_VIEW = PipelineView(
    included=PIPELINE_INCLUDED,
    excluded=PIPELINE_EXCLUDED,
    composite_definition=(
        "The composite this platform reports is the Round 3 definition: a Winsorized "
        "standard-deviation weighting over the developability components, recomputed per "
        "application route because each route carries a different weighting profile. The "
        "components, their normalised values and the weight each received are returned with "
        "every score so the number can be reproduced by hand."
    ),
    excluded_note=(
        "Rounds 5-8 concern 3D structure and are out of MVP scope. Because Round 7 also "
        "produced something called a composite score, the old frontend carried two "
        "definitions of the same term simultaneously; only the Round 3 definition is "
        "implemented here."
    ),
)

# ---------------------------------------------------------------------------
# Directions
# ---------------------------------------------------------------------------
#
# Display metadata only. Counts, status and availability are read from the database — the
# frontend previously hardcoded them as antioxidant 250 / antimicrobial 250 /
# anti-inflammatory 0 / anti-melanin 0 against an actual 170 / 65 / 154 / 107.
#
# The id is `antibacterial`, matching the stored direction value. The frontend called it
# "antimicrobial" while the predictors behind it are antibacterial classifiers
# (iMFP-LG's AMP channel and AMPlify), so the narrower and accurate name is used.

DIRECTION_META: list[dict[str, Any]] = [
    {
        "id": "antioxidant",
        "name": "Antioxidant",
        "icon": "shield-check",
        "color": "#10b981",
        "description": (
            "Peptides screened for free-radical scavenging for wound dressings, tissue "
            "engineering and antioxidant coatings. Ranked by AnOxPePred's FRS head."
        ),
        "functional_predictor": "AnOxPePred (FRS head)",
    },
    {
        "id": "antibacterial",
        "name": "Antibacterial",
        "icon": "shield-alert",
        "color": "#0ea5e9",
        "description": (
            "Peptides screened for antibacterial activity for anti-infection dressings and "
            "medical device coatings. Ranked by iMFP-LG's AMP channel, cross-checked against "
            "AMPlify-ESM."
        ),
        "functional_predictor": "iMFP-LG (AMP channel)",
    },
    {
        "id": "anti_inflammatory",
        "name": "Anti-inflammatory",
        "icon": "zap",
        "color": "#f59e0b",
        "description": (
            "Peptides screened for anti-inflammatory activity for chronic wound management. "
            "The AIP models behind this direction separate functional-looking peptides from "
            "random fragments rather than measuring anti-inflammatory activity, so the score "
            "is a ranking signal and is never presented as a probability."
        ),
        "functional_predictor": "iMFP-LG (AIP channel)",
    },
    {
        "id": "antimelanin",
        "name": "Anti-melanin Deposition",
        "icon": "sun",
        "color": "#8b5cf6",
        "description": (
            "Peptides screened for tyrosinase inhibition for skin-brightening functional "
            "materials. Ranked by TIPred."
        ),
        "functional_predictor": "TIPred",
    },
]

DIRECTIONS_BY_ID = {d["id"]: d for d in DIRECTION_META}

# Precursor counts: how many peptides each direction's functional predictor actually
# scored. Read from the enrichment table rather than restated — every tool rows over the
# full 20,248,885-peptide library except the MHC ones.
PRECURSOR_COUNT_NOTE = (
    "Counts the rows the direction's functional predictor holds in the enrichment table. "
    "Every functional predictor covers the full 20,248,885-peptide library."
)


# ---------------------------------------------------------------------------
# Static lookups the frontend renders
# ---------------------------------------------------------------------------

MATERIAL_FORM_OPTIONS: list[MaterialFormOption] = [
    MaterialFormOption(id=MaterialForm.lyophilized, label="Lyophilised sponge"),
    MaterialFormOption(id=MaterialForm.self_assembled_hydrogel, label="Self-assembled hydrogel"),
    MaterialFormOption(id=MaterialForm.injectable_gel, label="Injectable gel"),
    MaterialFormOption(id=MaterialForm.film, label="Film"),
    MaterialFormOption(id=MaterialForm.fiber, label="Fibre"),
    MaterialFormOption(id=MaterialForm.sheet, label="Sheet"),
    MaterialFormOption(id=MaterialForm.solution, label="Solution formulation"),
]

CATEGORY_LABELS = {
    "spider-silk": "Spider silk",
    "silkworm-silk": "Silkworm silk",
    "recombinant-collagen": "Recombinant collagen",
}

EVIDENCE_LEVELS = [
    {"id": "E1", "label": "E1", "description": "Purified protein, physicochemical or cell-free work"},
    {"id": "E2", "label": "E2", "description": "Cell work"},
    {"id": "E3", "label": "E3", "description": "Animal work"},
    {"id": "E4", "label": "E4", "description": "Human use or a controlled clinical study"},
    {"id": "E5", "label": "E5", "description": "Regulatory review and post-market safety data"},
]


def route_with_scaffolds(route: DeliveryRoute, scaffold_ids: list[str]) -> DeliveryRoute:
    """Attach the scaffolds the database admits for this route.

    Derived from `scaffold_library.route_ids` rather than from a hand-maintained array, so
    the route-to-scaffold relation exists in exactly one direction.
    """
    return route.model_copy(update={"scaffold_ids": scaffold_ids})


def build_directions(counts: dict[str, dict[str, Any]],
                     precursor_counts: dict[str, int]) -> list[FunctionDirection]:
    """Combines display metadata with the real counts read from `constructs`."""
    out: list[FunctionDirection] = []
    for meta in DIRECTION_META:
        c = counts.get(meta["id"], {})
        total = int(c.get("total", 0))
        by_status: dict[str, int] = c.get("by_status", {}) or {}
        passed = int(by_status.get("passed", 0))

        # `ready` requires ranked constructs that the pipeline signed off. A direction whose
        # rows are all still WIP is reported as `wip` even though it holds 100+ constructs,
        # which is the distinction the frontend previously could not express: it showed
        # anti-inflammatory and anti-melanin as empty directories while showing
        # antibacterial as ready with 250 entries, against an actual 65.
        if total == 0:
            status = "empty"
        elif passed > 0:
            status = "ready"
        else:
            status = "wip"

        out.append(FunctionDirection(
            id=meta["id"],
            name=meta["name"],
            icon=meta["icon"],
            color=meta["color"],
            description=meta["description"],
            precursor_count=precursor_counts.get(meta["id"], 0),
            construct_count=total,
            status=status,
            counts={
                "total": total,
                "top": int(c.get("top", 0)),
                "bottom": int(c.get("bottom", 0)),
                "by_status": by_status,
            },
        ))
    return out


def scaffold_categories(route_map: dict[str, list[str]]) -> list[ScaffoldCategoryView]:
    """Categories are a scaffold property, so the grouping is assembled by the caller from
    scaffold rows; this helper only provides the label table."""
    return []
