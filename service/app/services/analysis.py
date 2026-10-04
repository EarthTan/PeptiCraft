"""Analysis text generation.

The generator is a protocol, not a function, so that a model-backed implementation can be
added later without the router, the response model or the frontend changing.

`TemplateGenerator` is the implementation registered today. It reads the construct's real
scores, the route's thresholds and the peptide's own attributes, and composes prose from
them. Determinism is the point: the same construct under the same route always renders the
same text, and every number in that text appears as a field in the same response, so a
reader can check any claim without running a query.

This replaces `app/src/data/chat.ts`, a 453-line module of fixed strings that was never
referenced by any page and had drifted well past the data — it still advertised a 32-linker
library, a 1,760 Da figure and "8 rounds of screening" long after the platform carried 15
linkers, no molecular-weight figure and four rounds.

`provider` travels on every response. When the LLM implementation is registered, that field
changes and the frontend can label the output accordingly rather than presenting template
prose as model output.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Protocol

from ..models.analysis import AnalysisBlock, ChatMessage, ChatResponse
from ..models.common import BackboneBinding, ScoreSemantics
from ..models.construct import ConstructDetail
from . import reference

PROVIDER_TEMPLATE = "template"


class AnalysisGenerator(Protocol):
    """Implemented by the template generator today and by an LLM generator later."""

    name: str

    def blocks(self, construct: ConstructDetail) -> list[AnalysisBlock]: ...

    def answer(self, construct: ConstructDetail, question: str) -> str: ...


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _pct(value: float | None) -> str:
    return "not assessed" if value is None else f"{value:.3f}"


def _verdict_word(verdict: str) -> str:
    return {
        "clear": "clears every assessed gate",
        "vetoed": "is stopped by a veto gate",
        "borderline": "clears every assessed gate but sits close to one",
        "indeterminate": "has no assessed veto gate and cannot be cleared or stopped",
    }.get(verdict, verdict)


def _route_name(route_id: str | None) -> str:
    route = reference.ROUTES_BY_ID.get(route_id or "")
    return route.name if route else "the selected route"


# The `antioxidant` slot of the nine-score grid holds whichever predictor ranks the
# construct's direction. The name is a leftover from a single-direction platform.
_FUNCTIONAL_SLOT = "antioxidant"


def _source_phrase(source: str) -> str:
    """How a threshold's origin reads inside a sentence.

    The service carries `tool` / `route` / `project` as tokens, which is right for a field
    and wrong for prose: "a threshold of 0.380 from tool" is not a sentence.
    """
    return {
        "tool": "the predictor's own cut-off",
        "route": "the route's screening profile",
        "project": "a platform-wide constant",
    }.get(source, source)


# ---------------------------------------------------------------------------
# Template implementation
# ---------------------------------------------------------------------------

class TemplateGenerator:
    name = PROVIDER_TEMPLATE

    def blocks(self, c: ConstructDetail) -> list[AnalysisBlock]:
        return [
            self._safety(c),
            self._peptide_origin(c),
            self._linker_rationale(c),
            self._expression_strategy(c),
            self._comparison(c),
            self._risk(c),
        ]

    # -- block 1 ------------------------------------------------------------
    def _safety(self, c: ConstructDetail) -> AnalysisBlock:
        gates = c.safety.gates
        # Which gates eliminate is read off the gate itself. Restating the key list here put
        # the rule in two places, and the two had already drifted apart once.
        veto = [g for g in gates if g.is_veto_gate]
        lines = [
            f"Under the {_route_name(c.safety.route_id)} profile, this construct "
            f"{_verdict_word(c.safety.verdict)}."
        ]

        for g in veto:
            if g.value is None:
                lines.append(
                    f"{g.label} has no measured value, so it is reported as not assessed "
                    f"rather than as a pass. The pipeline's rule is that an unassessed metric "
                    f"does not eliminate a candidate."
                )
            else:
                # The failing side depends on the metric. Most gates fail on a high value;
                # the MHC-II percent rank fails on a low one, because a low percent rank is
                # a stronger binder.
                if g.higher_is_better:
                    side = "at or above" if g.passed else "below"
                else:
                    side = "at or below" if g.passed else "above"
                lines.append(
                    f"{g.label} ({g.tool}) measures {_pct(g.value)} against a threshold of "
                    f"{_pct(g.threshold)} from {_source_phrase(g.threshold_source)}, which is "
                    f"{side} the limit."
                    + (" The value sits within ten percent of the threshold." if g.borderline else "")
                )

        soft = [g for g in gates if not g.is_veto_gate]
        if soft:
            assessed_soft = [g for g in soft if g.value is not None]
            if assessed_soft:
                lines.append(
                    "Soft signals, which do not veto: "
                    + "; ".join(
                        f"{g.label} {_pct(g.value)}"
                        + (f" (threshold {_pct(g.threshold)})" if g.threshold else "")
                        for g in assessed_soft
                    )
                    + "."
                )

        if c.safety.verdict == "vetoed":
            lines.append(
                "Because the pipeline applies no weighted compensation to veto gates, a "
                "single failure removes the candidate outright."
            )

        return AnalysisBlock(
            id="safety",
            type="safety",
            title="Safety reading",
            icon="shield",
            content="\n".join(lines),
            citations=[
                "safety.verdict",
                "safety.gates[].value",
                "safety.gates[].threshold",
                "safety.immunogenicity_threshold",
            ],
        )

    # -- block 2 ------------------------------------------------------------
    def _peptide_origin(self, c: ConstructDetail) -> AnalysisBlock:
        p = c.peptide
        seq = p.sequence
        length = len(seq)

        hydrophobic = set("AVILMFWY")
        charged = set("DEKRH")
        aromatic = set("FWY")
        cys = seq.count("C")

        hyd = sum(1 for a in seq if a in hydrophobic)
        chg = sum(1 for a in seq if a in charged)
        arom = sum(1 for a in seq if a in aromatic)

        lines = [
            f"The peptide is {length} residues, drawn from {p.source} "
            f"(dataset version {p.source_version}).",
            f"Composition: {hyd} hydrophobic residues ({hyd / length:.0%}), "
            f"{chg} charged ({chg / length:.0%}), {arom} aromatic ({arom / length:.0%}).",
        ]

        if cys:
            lines.append(
                f"{cys} cysteine residue{'s' if cys > 1 else ''} present, which allows "
                f"disulfide formation and can stiffen the peptide against proteolysis."
            )
        else:
            lines.append(
                "No cysteine residues, so the peptide has no disulfide-mediated structural "
                "constraint."
            )

        if c.supplementary.aggregation_a3v is not None:
            agg = c.supplementary.aggregation_a3v
            reading = (
                "below zero, which indicates a low intrinsic aggregation propensity"
                if agg < 0
                else "above zero, which indicates some aggregation propensity"
            )
            lines.append(
                f"One-dimensional AGGRESCAN gives {agg:.3f}, {reading}. The scale is a mean "
                f"per-residue aggregation score, negative for aggregation-averse sequences."
            )

        # The predictor is named from the score grid's own metadata. This block used to hold a
        # third hand-written key-to-name table, and it was both incomplete and wrong: the
        # antibacterial key is `amp-esm`, which the table did not carry, so the sentence read
        # "The functional score of 0.848 is amp-esm from amp-esm."
        func_meta = c.score_meta.get(_FUNCTIONAL_SLOT)
        predictor = func_meta.tool if func_meta else c.functional_score_label
        lines.append(
            f"The direction's functional score is {_pct(c.functional_score)}, produced by "
            f"{predictor or c.functional_score_key}."
        )
        if c.semantics == ScoreSemantics.ranking_only:
            lines.append(
                "That score is a ranking signal, not a probability. It separates "
                "functional-looking peptides from random fragments rather than measuring "
                "activity, so it is used for ordering only."
            )

        return AnalysisBlock(
            id="peptide_origin",
            type="peptide_origin",
            title="Peptide origin and composition",
            icon="dna",
            content="\n".join(lines),
            citations=[
                "peptide.sequence",
                "peptide.source",
                "peptide.source_version",
                "supplementary.aggregation_a3v",
                "functional_score",
            ],
        )

    # -- block 3 ------------------------------------------------------------
    def _linker_rationale(self, c: ConstructDetail) -> AnalysisBlock:
        lines = []
        if c.linker is None:
            lines.append("No linker is recorded for this construct.")
        else:
            lk = c.linker
            lines.append(
                f"The linker is {lk.name}, {lk.length} residues long, classified as "
                f"{lk.rigidity}."
            )
            lines.append(
                "A glycine-serine linker of this kind gives the fused peptide rotational "
                "freedom and separates it from the scaffold surface, which matters when the "
                "functional epitope would otherwise be masked by the scaffold. The trade-off "
                "is that the unstructured segment is more exposed to proteases."
            )
            lines.append(
                "The linker sequence recorded here comes from the sample linker table rather "
                "than the curated library, and the construct carries no verified linker "
                "choice: the assembly step that produced it picked the first available row."
            )

        # The three binding states read differently, and saying "named at request time" for a
        # verified stored binding would be a factual error: the scaffold came from the
        # construct's own row.
        if not c.assembled_sequence_available:
            assembly_reading = (
                "No fused sequence is emitted, because the bound scaffold row holds a marker "
                "string rather than a real sequence."
            )
        elif c.backbone_binding == BackboneBinding.verified:
            assembly_reading = (
                "A fused sequence is emitted, assembled from the scaffold sequence recorded "
                "against this construct."
            )
        else:
            assembly_reading = (
                "A fused sequence is emitted, using a scaffold named at request time."
            )

        lines.append(
            f"The construct's stored scaffold binding is `{c.backbone_binding}`. "
            + assembly_reading
        )

        return AnalysisBlock(
            id="linker_rationale",
            type="linker_rationale",
            title="Linker and assembly",
            icon="link",
            content="\n".join(lines),
            citations=["linker.name", "linker.length", "linker.rigidity", "backbone_binding"],
        )

    # -- block 4 ------------------------------------------------------------
    def _expression_strategy(self, c: ConstructDetail) -> AnalysisBlock:
        lines = [
            "No expression host, vector or induction condition is recorded against this "
            "construct. The dataset does not carry that field, so nothing is asserted here.",
        ]
        if c.scaffold is not None:
            lines.append(
                f"The scaffold is {c.scaffold.short_name}, developed by {c.scaffold.applicant}"
                + (f" (patent {c.scaffold.patent})" if c.scaffold.patent else "")
                + f", with a highest evidence level of {c.scaffold.max_evidence}."
            )
        elif c.backbone_name:
            lines.append(
                f"The scaffold recorded against this construct is {c.backbone_name}. It carries "
                f"a real sequence, which is what the fused assembly uses, but it is not one of "
                f"the curated scaffold-library entries, so no applicant, patent or evidence "
                f"level is attached to it."
            )
        if c.scores.solubility is not None:
            lines.append(
                f"Predicted solubility is {_pct(c.scores.solubility)} (SoDoPE). Recombinant "
                f"yield is the practical constraint that this score stands in for: a low "
                f"value typically means the construct partitions into inclusion bodies and "
                f"needs refolding rather than a straightforward soluble purification."
            )
        else:
            lines.append("Solubility was not assessed for this peptide.")

        if c.scores.thermal_stability is not None:
            lines.append(
                f"Predicted thermal stability is {_pct(c.scores.thermal_stability)} "
                f"(TemStaPro), relevant to storage and to any formulation step that involves "
                f"heating."
            )

        return AnalysisBlock(
            id="expression_strategy",
            type="expression_strategy",
            title="Expression and handling",
            icon="flask",
            content="\n".join(lines),
            citations=[
                "scaffold.short_name",
                "scaffold.applicant",
                "scores.solubility",
                "scores.thermal_stability",
            ],
        )

    # -- block 5 ------------------------------------------------------------
    def _comparison(self, c: ConstructDetail) -> AnalysisBlock:
        rows = _direction_peers(c.direction, limit=5)
        lines = [
            f"Peers within the {c.direction_label} direction, ordered by composite under "
            f"{_route_name(c.safety.route_id)}. The composite is a ranking score computed "
            f"from developability components, so a higher value means a better combination "
            f"of penetration, solubility and thermal stability rather than stronger activity."
        ]
        for i, peer in enumerate(rows, 1):
            marker = " ← this construct" if peer["id"] == c.id else ""
            lines.append(
                f"{i}. {peer['name']} — composite {_pct(peer['composite'])}, "
                f"functional {_pct(peer['functional_score'])}, "
                f"toxicity {_pct(peer['toxicity'])}, haemolysis {_pct(peer['hemolysis'])}{marker}"
            )
        return AnalysisBlock(
            id="comparison",
            type="comparison",
            title="Comparison within the direction",
            icon="bar-chart",
            content="\n".join(lines),
            citations=["composite", "functional_score", "scores.toxicity", "scores.hemolysis"],
        )

    # -- block 6 ------------------------------------------------------------
    def _risk(self, c: ConstructDetail) -> AnalysisBlock:
        lines = []
        if c.unassessed_metrics:
            lines.append(
                "Not assessed for this construct: " + ", ".join(c.unassessed_metrics) + "."
            )
        else:
            lines.append("Every metric in the nine-score contract has a measured value.")

        if c.safety.unassessed:
            lines.append(
                "Veto gates without a measurement: " + ", ".join(c.safety.unassessed)
                + ". These are reported as unassessed rather than as passing."
            )

        if not c.assembled_sequence_available:
            lines.append(
                "No fused sequence is available, because the scaffold binding is a "
                "placeholder. Any downstream step that needs the full construct sequence "
                "cannot proceed on this record."
            )

        if c.status == "WIP":
            lines.append(
                "The construct carries the status WIP. Its direction has not been signed off, "
                "so its rank should not be read as a settled ordering."
            )

        if c.channel == "bottom":
            lines.append(
                "This construct sits in the bottom channel, which exists as a negative "
                "control for comparison rather than as a candidate."
            )

        return AnalysisBlock(
            id="risk",
            type="risk",
            title="Risk register",
            icon="alert",
            content="\n".join(lines),
            citations=["unassessed_metrics", "safety.unassessed", "status", "channel"],
        )

    # -- chat ---------------------------------------------------------------
    def answer(self, c: ConstructDetail, question: str) -> str:
        q = question.lower().strip()

        if any(w in q for w in ("safe", "safety", "tox", "hemo", "immun", "gate")):
            return self._safety(c).content
        if any(w in q for w in ("sequence", "assembl", "backbone", "scaffold", "fuse")):
            return self._linker_rationale(c).content
        if any(w in q for w in ("solubility", "express", "purif", "yield", "stability", "thermal")):
            return self._expression_strategy(c).content
        if any(w in q for w in ("origin", "source", "composit", "peptide")):
            return self._peptide_origin(c).content
        if any(w in q for w in ("compare", "rank", "best", "peer", "composite")):
            return self._comparison(c).content
        if any(w in q for w in ("risk", "caveat", "unassess", "missing", "limit")):
            return self._risk(c).content

        return (
            f"This answer is generated from the record for {c.name} rather than from a "
            f"language model, so it covers the fields the record actually holds. Available "
            f"topics: the safety gates and the route's immunogenicity threshold; the peptide's "
            f"origin and composition; the linker and the state of the scaffold binding; "
            f"solubility and thermal stability; the comparison with peers in the same "
            f"direction; and the construct's unassessed metrics. "
            f"Current composite under {_route_name(c.safety.route_id)}: {_pct(c.composite)}."
        )

    def suggested_questions(self, c: ConstructDetail) -> list[str]:
        out = [
            "How does the safety gate read under this route?",
            "Which metrics were not assessed?",
            "What is the state of the scaffold binding?",
        ]
        if c.semantics == ScoreSemantics.ranking_only:
            out.append("Why is the functional score a ranking signal rather than a probability?")
        return out


def _direction_peers(direction: str, limit: int = 5) -> list[dict]:
    """Top constructs of the same direction, for the comparison block.

    Runs the same computation the detail response uses, so a peer row cannot disagree with
    that construct's own page about a score.

    Imported lazily: the analysis service is constructed by the router, and importing the
    construct service at module scope would close a cycle between the two.
    """
    from ..repositories import constructs as repo
    from . import constructs as construct_service

    rows, _ = repo.list_constructs(direction=direction, channel="top", limit=limit, offset=0)
    if not rows:
        return []
    enriched = construct_service.load_enrichment(rows)
    out = []
    for row in rows:
        a = construct_service.compute(row, enriched.get(row["peptide_id"], {}), None)
        out.append({
            "id": construct_service.public_id(row["id"]),
            "name": construct_service.public_id(row["id"]),
            "composite": a.scores.composite,
            "functional_score": a.functional_value,
            "toxicity": a.scores.toxicity,
            "hemolysis": a.scores.hemolysis,
        })
    return out


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_generator: AnalysisGenerator = TemplateGenerator()


def get_generator() -> AnalysisGenerator:
    return _generator


def register_generator(generator: AnalysisGenerator) -> None:
    """Swap in another implementation, such as a model-backed one."""
    global _generator
    _generator = generator


def llm_configured() -> bool:
    from ..config import get_settings
    s = get_settings()
    return bool(s.llm_base_url and s.llm_api_key and s.analysis_provider == "llm")


def build_response(c: ConstructDetail) -> tuple[str, list[AnalysisBlock]]:
    g = get_generator()
    return g.name, g.blocks(c)


def chat(c: ConstructDetail, question: str) -> ChatResponse:
    g = get_generator()
    content = g.answer(c, question)
    message = ChatMessage(
        id=f"msg_{uuid.uuid4().hex[:12]}",
        role="assistant",
        content=content,
        timestamp=datetime.now(timezone.utc).isoformat(),
        actions=[],
    )
    suggested = getattr(g, "suggested_questions", None)
    return ChatResponse(
        provider=g.name,
        construct_id=c.id,
        message=message,
        suggested_questions=suggested(c) if callable(suggested) else [],
        llm_configured=llm_configured(),
    )
