"""Score assembly, composite computation and safety evaluation.

The composite follows the pipeline's own Round 3 definition as implemented in
`iGEM-platform-main/src/pipeline/antioxidant/scoring.py`, with one correction.

What the pipeline does:

    components  = {cpp: plm4cpps, sens: algpred2, epitope: bepipred, agg: aggrescan_a3v}
                  each normalised to [0,1] and flipped so that higher is always better
    weights     = the Winsorized standard deviation of each component over the direction's
                  top channel, normalised to sum to 1 — spread decides weight, so a
                  genuinely discriminative component is up-weighted and a flat one is
                  automatically down-weighted, all without a hand-set preset
    composite   = sum(weight_k * component_k * multiplier_k) * alpha

The correction concerns the multipliers. The pipeline declares

    DELIVERY = {"topical": {"cpp": 1.4, "sol": 1.3, "thermal": 0.7}, ...}

but applies them with `multiplier.get(k, 1.0)` while iterating over the *weights* dict,
whose keys are `cpp`, `sens`, `epitope` and `agg`. The keys `sol` and `thermal` therefore
never match, and those multipliers have never taken effect — only `cpp` ever receives one.
The same mismatch means the per-delivery differentiation the design intends is essentially
absent: three of the four deliveries produce near-identical scores.

This service keeps the three components the delivery multipliers were written against —
`cpp` (pLM4CPPs), `solubility` (SoDoPE) and `thermalStability` (TemStaPro) — because those
are exactly the three the application routes carry weight tiers for, and applies the route's
tier multipliers to them for real. The three remaining components (`sens`, `epitope`, `agg`)
stay in the weighted sum at a multiplier of 1.0, so their data-driven contribution is
preserved without diluting the route profile.

Everything the composite is built from is returned with the score: the normalised component
values, the weight each received, the route multiplier each received, and the pool the
normalisation was taken over. A reviewer can reproduce any composite from a single response
without re-running a query.
"""
from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from ..models.common import AppliedThreshold, ScoreMeta, ScoreSemantics
from ..models.construct import (
    ConstructScores,
    DeliveryAdjustedScores,
    SafetyGate,
    SafetyVerdict,
    SupplementaryScores,
)
from ..repositories import constructs as constructs_repo
from ..repositories import enrichment
from . import reference

log = logging.getLogger("pepticraft.scoring")

# ---------------------------------------------------------------------------
# Component definitions
# ---------------------------------------------------------------------------
#
# (name, enrichment tool, higher_is_better). `agg` reads from constructs.scores rather than
# the enrichment table, because one-dimensional AGGRESCAN is computed by the pipeline at
# assembly time and was never loaded as an enrichment tool: a `tool = 'aggrescan'` query
# returns zero rows.

COMPONENTS: tuple[tuple[str, str | None, bool], ...] = (
    ("cpp", enrichment.PLM4CPPS, True),
    ("solubility", enrichment.SODOPE, True),
    ("thermal", enrichment.TEMSTAPRO, True),
    ("sens", enrichment.ALGPRED2, False),
    ("epitope", enrichment.BEPIPRED3, False),
    ("agg", None, False),          # from constructs.scores.aggrescan_a3v
)

# Which components a route's weight tiers apply to, and the key its multiplier is stored
# under in the route definition.
ROUTE_WEIGHTED = ("cpp", "solubility", "thermal")

ALPHA = 1.0


@dataclass
class PoolStats:
    """Normalisation bounds and component weights for one direction.

    Pool-relative by design, matching the pipeline: a component that varies widely across
    the candidate pool is doing discriminating work and earns weight, while one that is
    nearly constant carries no information and is down-weighted automatically.
    """

    direction: str
    size: int
    bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    coverage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "size": self.size,
            "weights": {k: round(v, 6) for k, v in self.weights.items()},
            "bounds": {k: [round(lo, 6), round(hi, 6)] for k, (lo, hi) in self.bounds.items()},
            "coverage": self.coverage,
        }


_cache: dict[str, PoolStats] = {}
_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Statistics helpers — ported from the pipeline so the numbers stay comparable
# ---------------------------------------------------------------------------

def winsorized_std(values: Sequence[float], lo: float = 0.05, hi: float = 0.95) -> float:
    """Standard deviation after clipping to the 5th and 95th percentile.

    Clipping first keeps a single extreme peptide from dominating the weight that a whole
    component receives. Fewer than two observations means no spread can be estimated, and
    the pipeline's answer of 0.0 — which removes the component from the sum — is kept.
    """
    clean = sorted(v for v in values if v is not None and not _is_nan(v))
    if len(clean) < 2:
        return 0.0
    lo_q, hi_q = _quantile(clean, lo), _quantile(clean, hi)
    clipped = [min(max(v, lo_q), hi_q) for v in clean]
    mean = sum(clipped) / len(clipped)
    variance = sum((v - mean) ** 2 for v in clipped) / (len(clipped) - 1)
    return math.sqrt(variance)


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile, matching pandas' default."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lower = int(math.floor(pos))
    upper = min(lower + 1, len(sorted_values) - 1)
    frac = pos - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


def _is_nan(v: Any) -> bool:
    return isinstance(v, float) and math.isnan(v)


def to_component(value: float | None, lo: float, hi: float, higher_is_better: bool) -> float | None:
    """Normalise to [0,1] and orient so higher is always better.

    A degenerate bound pair (every value identical across the pool) becomes 0.5 — the
    pipeline's neutral answer — because min-max normalisation has nothing to divide by and
    the component carries no signal anyway.
    """
    if value is None or _is_nan(value):
        return None
    if hi == lo:
        return 0.5
    n = (value - lo) / (hi - lo)
    n = min(max(n, 0.0), 1.0)
    return n if higher_is_better else 1.0 - n


# ---------------------------------------------------------------------------
# Pool loading
# ---------------------------------------------------------------------------

def _raw_component_values(direction: str) -> tuple[dict[str, list[float]], int, dict[str, int]]:
    """Read the direction's top channel and return raw component values.

    The top channel is the ranking pool the pipeline weighted against. Roughly 60-115 rows
    per direction, so this is a pair of small queries and the result is cached.
    """
    rows, _ = constructs_repo.list_constructs(
        direction=direction, channel="top", limit=1000, offset=0
    )
    if not rows:
        return {}, 0, {}

    peptide_ids = [r["peptide_id"] for r in rows]
    scored = enrichment.scores_for_peptides(
        peptide_ids, [t for _, t, _ in COMPONENTS if t]
    )

    values: dict[str, list[float]] = {name: [] for name, _, _ in COMPONENTS}
    coverage: dict[str, int] = {name: 0 for name, _, _ in COMPONENTS}

    for row in rows:
        enriched = scored.get(row["peptide_id"], {})
        stored = constructs_repo.scores_of(row)
        for name, tool, _ in COMPONENTS:
            if tool is None:
                raw = _as_float(stored.get("aggrescan_a3v"))
            else:
                entry = enriched.get(tool)
                raw = _as_float(entry["score"]) if entry else None
            if raw is not None:
                values[name].append(raw)
                coverage[name] += 1

    return values, len(rows), coverage


def pool_stats(direction: str, *, refresh: bool = False) -> PoolStats:
    with _cache_lock:
        if not refresh and direction in _cache:
            return _cache[direction]

    values, size, coverage = _raw_component_values(direction)
    stats = PoolStats(direction=direction, size=size, coverage=coverage)

    if size == 0:
        return stats

    raw_weights: dict[str, float] = {}
    for name, _, higher_is_better in COMPONENTS:
        series = values.get(name) or []
        if not series:
            raw_weights[name] = 0.0
            continue
        # Bounds are taken on the raw values before orientation, so that a
        # lower-is-better component is normalised against its own range and only then
        # flipped.
        stats.bounds[name] = (min(series), max(series))
        raw_weights[name] = winsorized_std(series)

    total = sum(raw_weights.values())
    if total == 0:
        stats.weights = {k: 0.0 for k in raw_weights}
    else:
        stats.weights = {k: v / total for k, v in raw_weights.items()}

    with _cache_lock:
        _cache[direction] = stats
    log.info(
        "pool stats for %s: size=%d weights=%s",
        direction, stats.size,
        {k: round(v, 4) for k, v in stats.weights.items()},
    )
    return stats


def _as_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


# ---------------------------------------------------------------------------
# Score assembly
# ---------------------------------------------------------------------------

# Functional score key per direction, taken from the key each direction's `select.py`
# actually ranked on:
#
#   antioxidant        the pool is cut at the aopxsvm P90, but aopxsvm's stored value is a
#                      class label (1) with the probability in `details.prob`, so the
#                      reported activity score is AnOxPePred's free-radical-scavenging head
#   antibacterial      amp-esm, which is AMPlify v0.1.0 over the whole library
#   anti_inflammatory   imfp_lg_AIP
#   antimelanin        tipred
#
# The semantics default here but are overridden by `func_score_meaning` when the stored
# scores carry it, because that field is the pipeline's own statement about what its number
# may be read as.
FUNCTIONAL_SCORE: dict[str, tuple[str, ScoreSemantics]] = {
    "antioxidant": (enrichment.ANOXPEPRED_FRS, ScoreSemantics.probability),
    "antibacterial": (enrichment.AMP_ESM, ScoreSemantics.probability),
    "anti_inflammatory": (enrichment.IMFP_LG_AIP, ScoreSemantics.ranking_only),
    "antimelanin": (enrichment.TIPRED, ScoreSemantics.ranking_only),
}

# The pooling key each direction used to build its candidate pool, reported alongside the
# activity score so the two are not confused. Antioxidant pools on aopxsvm, which is a
# classifier output rather than a probability.
POOLING_KEY: dict[str, str] = {
    "antioxidant": enrichment.AOPXSVM,
    "antibacterial": enrichment.AMP_ESM,
    "anti_inflammatory": enrichment.IMFP_LG_AIP,
    "antimelanin": enrichment.TIPRED,
}

_SEMANTICS_BY_STORED_VALUE = {
    "ranking_only_not_probability": ScoreSemantics.ranking_only,
    "probability": ScoreSemantics.probability,
}

# Keys in the nine-score contract that are veto gates. Three, not four: B-cell epitope
# propensity is a soft signal, which is what the pipeline's Round 2 and the analysis
# module's own `anyVeto` both say.
VETO_GATES = ("toxicity", "hemolysis", "immunogenicity")


def functional_score(
    direction: str,
    enriched: dict[str, dict[str, Any]],
    stored: dict[str, Any] | None = None,
) -> tuple[float | None, str, ScoreSemantics]:
    """The direction's activity score, its key, and what that number may be read as.

    `func_score_meaning` in the stored scores wins over the default when present: three of
    the four directions carry it, and it is the pipeline's own statement that the value is a
    ranking signal. Anti-inflammatory and anti-melanin rows all carry
    `ranking_only_not_probability`, which is why a score from those directions is never
    rendered as a probability or a confidence.
    """
    key, default_semantics = FUNCTIONAL_SCORE.get(
        direction, (enrichment.ANOXPEPRED_FRS, ScoreSemantics.probability)
    )
    semantics = default_semantics
    if stored:
        stored_meaning = stored.get("func_score_meaning")
        if isinstance(stored_meaning, str) and stored_meaning in _SEMANTICS_BY_STORED_VALUE:
            semantics = _SEMANTICS_BY_STORED_VALUE[stored_meaning]

    entry = enriched.get(key)
    return (_as_float(entry["score"]) if entry else None), key, semantics


def assemble_scores(
    direction: str,
    stored: dict[str, Any],
    enriched: dict[str, dict[str, Any]],
) -> tuple[ConstructScores, SupplementaryScores, dict[str, ScoreMeta], ScoreSemantics]:
    """Build the nine scores plus the supplementary measurements and per-score metadata."""

    func_value, func_key, semantics = functional_score(direction, enriched, stored)

    def from_tool(tool: str) -> float | None:
        entry = enriched.get(tool)
        return _as_float(entry["score"]) if entry else None

    # B-cell epitope: the current predictor writes `bepipred3` into the enrichment table
    # while the 170 antioxidant rows also carry an older `bepipred` key in constructs.scores.
    # The enrichment value is preferred; the stored one is the fallback.
    epitope = from_tool(enrichment.BEPIPRED3)
    if epitope is None:
        epitope = _as_float(stored.get("bepipred"))

    # The `antioxidant` slot holds the direction's functional score. The name is a leftover
    # from a single-direction platform, and the four directions are ranked by four different
    # predictors, so the field would be null for three quarters of the library if it were
    # taken literally. The slot is kept because it is the functional position in the
    # frontend's score grid, and `score_meta["antioxidant"]` is rewritten below to name the
    # predictor actually behind the number. `functional_score` and `functional_score_key`
    # carry the same value without ambiguity for any caller that does not need the grid.
    scores = ConstructScores(
        antioxidant=func_value,
        toxicity=from_tool(enrichment.TOXINPRED3),
        hemolysis=from_tool(enrichment.HEMOPI2),
        immunogenicity=from_tool(enrichment.MHCFLURRY),
        b_cell_epitope=epitope,
        thermal_stability=from_tool(enrichment.TEMSTAPRO),
        solubility=from_tool(enrichment.SODOPE),
        cpp=from_tool(enrichment.PLM4CPPS),
        composite=None,   # filled per route
    )

    supplementary = SupplementaryScores(
        immunogenicity_ii_pct_rank=_as_float(stored.get("netmhcipan_min_rank_pct")
                                             if stored.get("netmhcipan_min_rank_pct") is not None
                                             else stored.get("netmhcipan_pctrank")),
        allergenicity=from_tool(enrichment.ALGPRED2),
        aggregation_a3v=_as_float(stored.get("aggrescan_a3v")),
        anoxpepred_frs=from_tool(enrichment.ANOXPEPRED_FRS),
        anoxpepred_chel=from_tool(enrichment.ANOXPEPRED_CHEL),
        aopxsvm=from_tool(enrichment.AOPXSVM),
        amp_esm=from_tool(enrichment.AMP_ESM),
        imfp_lg_amp=from_tool(enrichment.IMFP_LG_AMP),
        imfp_lg_aip=from_tool(enrichment.IMFP_LG_AIP),
        tipred=from_tool(enrichment.TIPRED),
    )

    # Metadata is keyed exactly as the score fields are, so a caller can pair
    # `scores.thermal_stability` with `score_meta["thermal_stability"]` without translating.
    # The tool reference data spells its keys the same way, so the field name is used
    # verbatim rather than derived.
    meta: dict[str, ScoreMeta] = {}
    for field, tool_def in reference.TOOLS_BY_KEY.items():
        if field == "composite":
            continue
        value = getattr(scores, field, None)

        # The functional slot is named by whichever predictor the direction is ranked on.
        if field == "antioxidant":
            tool_name = functional_label(func_key)
            meta[field] = ScoreMeta(
                key=field,
                tool=tool_name,
                measures=_FUNCTIONAL_TOOL_MEASURES.get(
                    func_key,
                    f"Functional activity score for the {direction} direction, from {func_key}.",
                ),
                higher_is_better=True,
                group="function",
                assessed=value is not None,
                semantics=semantics,
                applied_threshold=_functional_threshold(func_key),
                is_veto_gate=False,
            )
            continue

        applied = None
        if tool_def.threshold is not None:
            applied = AppliedThreshold(
                value=tool_def.threshold,
                source=tool_def.threshold_source or "tool",
                note=tool_def.threshold_note,
            )
        meta[field] = ScoreMeta(
            key=field,
            tool=tool_def.tool,
            measures=tool_def.measures,
            higher_is_better=tool_def.higher_is_better,
            group=tool_def.group,
            assessed=value is not None,
            semantics=ScoreSemantics(tool_def.semantics),
            applied_threshold=applied,
            is_veto_gate=tool_def.is_veto_gate,
        )

    return scores, supplementary, meta, semantics


_FUNCTIONAL_TOOL_LABEL = {
    enrichment.ANOXPEPRED_FRS: "AnOxPePred (FRS head)",
    enrichment.AMP_ESM: "AMPlify v0.1.0",
    enrichment.IMFP_LG_AIP: "iMFP-LG (AIP channel)",
    enrichment.TIPRED: "TIPred",
}


def functional_label(tool_key: str) -> str:
    """The predictor's name for display, falling back to the key it was stored under.

    The keys are the pipeline's own tool identifiers and do not share a spelling convention,
    so they are carried as identifiers and rendered through this map.
    """
    return _FUNCTIONAL_TOOL_LABEL.get(tool_key, tool_key)

_FUNCTIONAL_TOOL_MEASURES = {
    enrichment.ANOXPEPRED_FRS: (
        "Probability that the peptide scavenges free radicals. The candidate pool was cut "
        "at the 90th percentile of AOPxSVM; this head is the reported activity measure."
    ),
    enrichment.AMP_ESM: (
        "Antibacterial activity from AMPlify v0.1.0, scored across the whole library and "
        "used as this direction's ranking key."
    ),
    enrichment.IMFP_LG_AIP: (
        "Anti-inflammatory signal from iMFP-LG's AIP channel. The model separates "
        "functional-looking peptides from random fragments rather than measuring "
        "anti-inflammatory activity, so this number orders candidates and is not a "
        "probability."
    ),
    enrichment.TIPRED: (
        "Tyrosinase-inhibitory activity from TIPred. The stored scores mark this direction "
        "as ranking-only."
    ),
}

_FUNCTIONAL_THRESHOLD_CACHE: dict[str, AppliedThreshold | None] = {}


def _functional_threshold(func_key: str) -> AppliedThreshold | None:
    """The predictor's own activity boundary, where it declares one."""
    if func_key in _FUNCTIONAL_THRESHOLD_CACHE:
        return _FUNCTIONAL_THRESHOLD_CACHE[func_key]
    spec = {
        enrichment.ANOXPEPRED_FRS: (0.5, "free-radical-scavenging head declares 0.5"),
        enrichment.TIPRED: (0.5, "TIPred declares 0.5"),
        enrichment.IMFP_LG_AIP: (0.5, "the AIP channel declares 0.5"),
    }.get(func_key)
    result = (
        AppliedThreshold(value=spec[0], source="tool", note=spec[1]) if spec else None
    )
    _FUNCTIONAL_THRESHOLD_CACHE[func_key] = result
    return result


# ---------------------------------------------------------------------------
# Composite per route
# ---------------------------------------------------------------------------

def composite_for(
    direction: str,
    scores: ConstructScores,
    supplementary: SupplementaryScores,
    route_id: str,
) -> DeliveryAdjustedScores:
    """Compute the composite under one route's weighting profile."""
    stats = pool_stats(direction)
    route = reference.ROUTES_BY_ID.get(route_id)
    if route is None:
        raise KeyError(f"unknown route {route_id!r}")

    tier_by_component = {
        "cpp": route.screening.cpp_weight,
        "solubility": route.screening.solubility_weight,
        "thermal": route.screening.thermal_stability_weight,
    }

    raw = {
        "cpp": scores.cpp,
        "solubility": scores.solubility,
        "thermal": scores.thermal_stability,
        "sens": supplementary.allergenicity,
        "epitope": scores.b_cell_epitope,
        "agg": supplementary.aggregation_a3v,
    }

    components: dict[str, float] = {}
    weights: dict[str, float] = {}
    multipliers: dict[str, float] = {}
    total = 0.0

    for name, _, higher_is_better in COMPONENTS:
        weight = stats.weights.get(name, 0.0)
        if weight <= 0:
            continue
        lo, hi = stats.bounds.get(name, (0.0, 1.0))
        norm = to_component(raw.get(name), lo, hi, higher_is_better)
        if norm is None:
            # An unassessed component drops out of the sum rather than counting as zero,
            # and the remaining weights are renormalised below so the scale stays intact.
            continue

        if name in ROUTE_WEIGHTED:
            tier = tier_by_component[name]
            mult = reference.WEIGHT_MULTIPLIER[tier.value]
        else:
            mult = 1.0

        components[name] = round(norm, 6)
        weights[name] = round(weight, 6)
        multipliers[name] = mult
        total += weight * mult

    if total == 0:
        value = None
    else:
        value = sum(
            weights[n] * multipliers[n] * components[n] for n in components
        ) / total * ALPHA

    return DeliveryAdjustedScores(
        cpp=scores.cpp,
        solubility=scores.solubility,
        thermal_stability=scores.thermal_stability,
        immunogenicity=scores.immunogenicity,
        composite=None if value is None else round(value, 6),
        components={**components, **{f"multiplier.{k}": v for k, v in multipliers.items()}},
        weights=weights,
    )


def composites_for_all_routes(
    direction: str,
    scores: ConstructScores,
    supplementary: SupplementaryScores,
) -> dict[str, DeliveryAdjustedScores]:
    return {
        route.id: composite_for(direction, scores, supplementary, route.id)
        for route in reference.ROUTES
    }


# ---------------------------------------------------------------------------
# Safety evaluation
# ---------------------------------------------------------------------------

BORDERLINE_BAND = 0.10

# NetMHCIIpan's conventional strong-binder cut, expressed in percent rank. The service adopts
# it as a reporting threshold; the pipeline itself carries the rank as a bare measurement and
# applies no cut of its own, so this number originates here rather than in the pipeline.
MHCII_STRONG_BINDER_RANK = 2.0


def evaluate_safety(
    scores: ConstructScores,
    supplementary: SupplementaryScores,
    route_id: str | None,
) -> SafetyVerdict:
    """Apply the veto gates under one route's immunogenicity threshold.

    Three gates are vetoes. The pipeline's null-passthrough rule is preserved: a metric
    eliminates a candidate only when it is present and out of bounds, and an unassessed
    metric eliminates nothing while still being reported as unassessed.

    The immunogenicity gate is the route's, not a global constant. Applying a single 0.50
    everywhere was the audit's first-priority correctness defect: a construct sitting at
    0.35 on the tightened routes was shown as clearing every gate.
    """
    route = reference.ROUTES_BY_ID.get(route_id) if route_id else None
    immuno_threshold = (
        route.screening.immunogenicity_threshold if route else None
    )

    gates: list[SafetyGate] = []

    def add(
        key: str,
        label: str,
        tool: str,
        value: float | None,
        threshold: float,
        threshold_source: str,
        *,
        note: str | None = None,
        higher_is_better: bool = False,
    ) -> None:
        # Both flags are derived from the gate's own definition rather than restated by each
        # caller, so the veto set and the failing direction travel with the gate.
        is_veto = key in VETO_GATES
        if value is None:
            gates.append(SafetyGate(
                key=key, label=label, tool=tool, value=None, threshold=threshold,
                threshold_source=threshold_source, passed=None,
                is_veto_gate=is_veto, higher_is_better=higher_is_better,
                note=note or "No measured value; the candidate is not eliminated on this gate.",
            ))
            return
        passed = value <= threshold if not higher_is_better else value >= threshold
        margin = abs(value - threshold)
        borderline = passed and margin <= threshold * BORDERLINE_BAND
        gates.append(SafetyGate(
            key=key, label=label, tool=tool, value=round(value, 6), threshold=threshold,
            threshold_source=threshold_source, passed=passed, borderline=borderline,
            is_veto_gate=is_veto, higher_is_better=higher_is_better,
            note=(
                f"Sits within {int(BORDERLINE_BAND * 100)}% of the threshold."
                if borderline else note
            ),
        ))

    tox_def = reference.TOOLS_BY_KEY["toxicity"]
    add("toxicity", "Toxicity", tox_def.tool, scores.toxicity, tox_def.threshold, "tool")

    hemo_def = reference.TOOLS_BY_KEY["hemolysis"]
    add("hemolysis", "Haemolysis", hemo_def.tool, scores.hemolysis, hemo_def.threshold, "tool")

    if immuno_threshold is not None:
        immuno_def = reference.TOOLS_BY_KEY["immunogenicity"]
        add(
            "immunogenicity", "Immunogenicity (MHC-I)", immuno_def.tool,
            scores.immunogenicity, immuno_threshold, "route",
            note=(
                f"Gate taken from the {route.name if route else 'selected'} route's screening "
                f"profile." if route else None
            ),
        )

    # Soft signals are reported beside the gates but never veto.
    epitope_def = reference.TOOLS_BY_KEY["b_cell_epitope"]
    if scores.b_cell_epitope is not None and epitope_def.threshold is not None:
        add(
            "b_cell_epitope", "B-cell epitope (soft)", epitope_def.tool,
            scores.b_cell_epitope, epitope_def.threshold, "tool",
            note="Soft signal, not a veto gate.",
        )

    # MHC-II travels as its own measurement because it is a percent rank, not a
    # probability, and cannot share the MHC-I gate.
    #
    # Direction matters and is the opposite of the MHC-I score. NetMHCIIpan reports a
    # percent rank where a low value means a stronger binder, and a strong MHC-II binder
    # is the pathway that recruits CD4+ T-helper cells, so the immunogenic reading is the
    # low one. The gate therefore passes on values *above* the strong-binder cut, which is
    # why it is the one gate built with `higher_is_better`.
    if supplementary.immunogenicity_ii_pct_rank is not None:
        add(
            "immunogenicity_ii", "Immunogenicity (MHC-II %)", "NetMHCIIpan",
            supplementary.immunogenicity_ii_pct_rank, MHCII_STRONG_BINDER_RANK, "project",
            higher_is_better=True,
            note=(
                "Percent rank, not a probability: lower means a stronger predicted binder, "
                f"and at or below {MHCII_STRONG_BINDER_RANK:g}% rank the peptide is a strong "
                "binder. Reported as a soft signal because coverage is partial."
            ),
        )

    veto_gates = [g for g in gates if g.key in VETO_GATES]
    failed = [g.key for g in veto_gates if g.passed is False]
    assessed = [g for g in veto_gates if g.passed is not None]
    borderline = [g.key for g in assessed if g.borderline]
    unassessed = [g.key for g in veto_gates if g.passed is None]

    if failed:
        verdict = "vetoed"
    elif not assessed:
        verdict = "indeterminate"
    elif borderline:
        verdict = "borderline"
    else:
        verdict = "clear"

    return SafetyVerdict(
        route_id=route_id,
        immunogenicity_threshold=immuno_threshold,
        verdict=verdict,
        gates=gates,
        unassessed=unassessed,
        vetoed_by=failed,
    )
