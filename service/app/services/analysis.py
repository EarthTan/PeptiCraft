"""Source-backed record analysis and actual conversational model generation.

Standing analysis blocks and explicit record mode remain deterministic. AI chat requires a
configured, successful model; failures are surfaced instead of substituted with fixed prose.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlsplit

from ..models.analysis import AnalysisBlock, ChatEvidence, ChatMessage, ChatResponse
from ..models.common import BackboneBinding, ScoreSemantics
from ..models.construct import ConstructDetail
from . import reference

log = logging.getLogger("pepticraft.analysis")

PROVIDER_TEMPLATE = "template"
PROVIDER_LLM = "llm"


class ModelUnavailable(RuntimeError):
    """Raised by a model-backed generator that could not produce an answer.

    Defined here rather than in the module that raises it so there is no import cycle —
    `llm` imports this module, not the other way round — and so the generator protocol and
    its failure mode are stated together.
    """


class LlmNotConfigured(ModelUnavailable):
    """AI mode was requested without a configured model endpoint, key and name."""


class AnalysisGenerator(Protocol):
    """Implemented by the template generator and by the model-backed one.

    `answer` takes the conversation so far. The template ignores it — it answers from the
    record, and there is nothing in a previous turn that changes what the record says — while a
    model-backed generator needs it to resolve a question like "and the one above it". The
    parameter is keyword-only with a default so a generator that does not need it can declare
    `answer(self, construct, question)` and still satisfy the protocol.

    `answer` raises `ModelUnavailable` when the generator cannot answer at all. A generator
    that always can — the template — never raises it.
    """

    name: str

    def blocks(self, construct: ConstructDetail) -> list[AnalysisBlock]: ...

    def answer(
        self, construct: ConstructDetail, question: str, *, history: list[dict[str, str]] | None = None
    ) -> str: ...


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _pct(value: float | None) -> str:
    return "not assessed" if value is None else f"{value:.6g}"


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

    def blocks(
        self, c: ConstructDetail, *, peers: list[dict] | None = None,
    ) -> list[AnalysisBlock]:
        return [
            self._safety(c),
            self._peptide_origin(c),
            self._linker_rationale(c),
            self._expression_strategy(c),
            self._comparison(c, peers=peers),
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
                    f"{g.label} has no predictor value (screening threshold {_pct(g.threshold)}), "
                    f"so it is reported as not assessed "
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
                    f"{g.label} ({g.tool}) reports {_pct(g.value)} against a threshold of "
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
        lines = [
            f"The peptide is {len(p.sequence)} residues, drawn from {p.source} "
            f"(dataset version {p.source_version}).",
            f"Sequence: {p.sequence}.",
        ]
        if p.source_accession:
            lines.append(f"Source accession: {p.source_accession}.")
        meta = c.score_meta.get(_FUNCTIONAL_SLOT)
        predictor = meta.tool if meta else c.functional_score_label
        lines.append(
            f"The direction's functional score is {_pct(c.functional_score)}, produced by "
            f"{predictor or c.functional_score_key}."
        )
        if c.semantics == ScoreSemantics.ranking_only:
            lines.append("That score is a ranking signal, not a probability or measured activity.")
        return AnalysisBlock(
            id="peptide_origin", type="peptide_origin", title="Peptide origin and composition",
            icon="dna", content="\n".join(lines),
            citations=["peptide.sequence", "peptide.source", "peptide.source_version", "functional_score"],
        )

    # -- block 3 ------------------------------------------------------------
    def _linker_rationale(self, c: ConstructDetail) -> AnalysisBlock:
        lines = [
            f"Scaffold: {c.backbone_name or 'none named'}"
            + (f" ({c.scaffold.id})" if c.scaffold else "") + "."
        ]
        if c.linker is None:
            lines.append("No linker is recorded for this construct.")
        else:
            lk = c.linker
            lines.append(
                f"The linker is {lk.name}, {lk.length} residues long, classified as "
                f"{lk.rigidity}; sequence: {lk.sequence}."
            )
            if lk.description:
                lines.append(f"Library description: {lk.description}")
            if c.linker_note:
                lines.append(c.linker_note)
            if lk.source_table == "linkers":
                lines.append(
                    "This linker comes from the sample linker table. Its stored assignment "
                    "is not evidence that this pairing was experimentally validated."
                )
            elif lk.reference:
                lines.append(f"Linker reference: {lk.reference}")

        # The three binding states read differently, and saying "named at request time" for a
        # verified stored binding would be a factual error: the scaffold came from the
        # construct's own row.
        if not c.assembled_sequence_available:
            assembly_reading = (
                "No fused sequence is emitted, because a complete scaffold sequence is "
                "unavailable for this selection."
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
            f"The scaffold binding for this response is `{c.backbone_binding.value}`. "
            + assembly_reading
        )
        if c.full_sequence:
            lines.append(f"The assembled sequence is {len(c.full_sequence)} residues long.")

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
        """Report sourced scaffold conditions without extrapolating them to the fusion."""
        expression = c.scaffold.expression if c.scaffold is not None else None
        lines: list[str] = []
        if expression is None or not any((
            expression.system, expression.vector_recorded, expression.vector_recommended,
            expression.rationale,
        )):
            lines.append(
                "No source-backed expression conditions are recorded for the selected scaffold. "
                "The current record cannot determine a host, strain, vector, induction "
                "temperature, duration or purification protocol for this fusion."
            )
        else:
            lines.append(
                f"Expression evidence for scaffold {c.scaffold.short_name}"
                + (f", sequence record {expression.sequence_id}" if expression.sequence_id else "")
                + ":"
            )
            for label, value in (
                ("Recorded/recommended host", expression.system),
                ("Vector recorded in source", expression.vector_recorded),
                ("Vector recommended in source", expression.vector_recommended),
                ("Basis and limitations (source wording)", expression.rationale),
            ):
                if value:
                    lines.append(f"{label}: {value}")
            if expression.source_url:
                lines.append(f"Source: {expression.source_url}")
            else:
                lines.append("No source URL is recorded for these expression fields.")
            lines.append(
                "These fields concern the cited scaffold sequence or family, within the "
                "source's stated limits. They do not establish expression conditions or "
                "yield for the scaffold–linker–peptide fusion."
            )
        lines.append(
            "Induction and purification conditions for the fusion require a matching "
            "experimental source or direct testing; peptide predictor scores cannot supply them."
        )
        return AnalysisBlock(
            id="expression_strategy", type="expression_strategy", title="Expression and handling",
            icon="flask", content="\n".join(lines), plan=None,
            citations=["scaffold.expression"],
        )

    # -- block 5 ------------------------------------------------------------
    def _comparison(self, c: ConstructDetail, *, peers: list[dict] | None = None) -> AnalysisBlock:
        rows = peers if peers is not None else _direction_peers(
            c.direction, limit=5, route_id=c.safety.route_id,
        )
        lines = [
            f"Peers within the {c.direction_label} direction, ordered by composite under "
            f"{_route_name(c.safety.route_id)}. The composite is a ranking score computed "
            f"from model signals using the project's weights. This is an exploratory ordering; "
            f"a higher value does not establish measured penetration, solubility, thermal "
            f"stability or activity."
        ]
        if not rows:
            lines.append("No peer records are available in this context, so no candidate comparison can be made.")
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
            lines.append("Every metric in the nine-score contract has a predictor value.")

        if c.safety.unassessed:
            lines.append(
                "Veto gates without a measurement: " + ", ".join(c.safety.unassessed)
                + ". These are reported as unassessed rather than as passing."
            )

        if not c.assembled_sequence_available:
            lines.append(
                "No fused sequence is available because a complete scaffold sequence is "
                "unavailable for this selection. Any downstream step needing the full sequence "
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
    def answer(
        self,
        c: ConstructDetail,
        question: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        return template_answer(c, question)[0]

    def suggested_questions(self, c: ConstructDetail) -> list[str]:
        out = [
            "How does the safety gate read under this route?",
            "Which metrics were not assessed?",
            "What is the state of the scaffold binding?",
            "What expression evidence is recorded for this scaffold?",
        ]
        if c.semantics == ScoreSemantics.ranking_only:
            out.append("Why is the functional score a ranking signal rather than a probability?")
        return out


def _direction_peers(direction: str, limit: int = 5, route_id: str | None = None) -> list[dict]:
    """Top constructs of the same direction, for the comparison block.

    Runs the same computation the detail response uses, so a peer row cannot disagree with
    that construct's own page about a score.

    Imported lazily: the analysis service is constructed by the router, and importing the
    construct service at module scope would close a cycle between the two.
    """
    from ..repositories import constructs as repo
    from . import constructs as construct_service

    rows, _ = repo.list_constructs(direction=direction, channel="top", limit=500, offset=0)
    if not rows:
        return []
    enriched = construct_service.load_enrichment(rows)
    out = []
    for row in rows:
        a = construct_service.compute(row, enriched.get(row["peptide_id"], {}), route_id)
        out.append({
            "id": construct_service.public_id(row["id"]),
            "name": construct_service.public_id(row["id"]),
            "composite": a.scores.composite,
            "functional_score": a.functional_value,
            "toxicity": a.scores.toxicity,
            "hemolysis": a.scores.hemolysis,
        })
    out.sort(key=lambda item: (
        item["composite"] is None,
        -(item["composite"] or 0.0),
        item["id"],
    ))
    return out[:limit]


# ---------------------------------------------------------------------------
# Record excerpts shared by deterministic analysis and model citations
# ---------------------------------------------------------------------------

class InvalidModelOutput(ModelUnavailable):
    """A completion failed the structured answer or fact/citation contract."""


def make_context_key(
    construct_id: str, route_id: str | None = None,
    scaffold_id: str | None = None, linker_id: str | None = None,
) -> str:
    return json.dumps([construct_id, route_id or "", scaffold_id or "", linker_id or ""], separators=(",", ":"))


def valid_source_url(value: str | None) -> str | None:
    if not value or any(character.isspace() for character in value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    return value if parsed.scheme in ("http", "https") and parsed.netloc else None


def build_claims(c: ConstructDetail) -> dict[str, ChatEvidence]:
    """Evidence excerpts for citations, separate from the model-generated answer."""
    template = TemplateGenerator()
    # Chat currently loads one candidate and has no peer fact tokens. The separate standing
    # analysis may compare peers, but that broader table must not leak into this chat context.
    blocks = {block.id: block for block in template.blocks(c, peers=[])}
    claims: dict[str, ChatEvidence] = {}

    def add(claim_id: str, label: str, text: str, field: str | None = None,
            kind: str = "record", url: str | None = None) -> None:
        claims[claim_id] = ChatEvidence(
            id=claim_id, label=label, text=text, kind=kind, field=field, url=url,
        )

    add("route", "Current context",
        f"Record {c.id}; application route: {_route_name(c.safety.route_id)} "
        f"({c.safety.route_id}). MHC-I screening threshold: "
        f"{_pct(c.safety.immunogenicity_threshold)}. Current route composite: {_pct(c.composite)}. "
        "The composite orders candidates under the project's selected weighting profile; "
        "its components have limited validation for short peptides. It is not a probability "
        "or a measured fusion-protein outcome.",
        "safety.route_id;composite")
    for claim_id, block_id, field in (
        ("safety", "safety", "safety"),
        ("provenance", "peptide_origin", "peptide;functional_score"),
        ("assembly", "linker_rationale", "scaffold;linker;backbone_binding;assembled_sequence_available"),
        ("linker", "linker_rationale", "linker;linker_note"),
        ("expression", "expression_strategy", "scaffold.expression"),
        ("missing", "risk", "unassessed_metrics;safety.unassessed;status;channel"),
    ):
        block = blocks[block_id]
        add(claim_id, block.title, block.content, field,
            "limitation" if claim_id == "missing" else "record")
    add("comparison", "Comparison needs another record",
        "Only the current candidate and its selected application, scaffold and linker are "
        "available to this chat. No other candidate records have been loaded for comparison. "
        "A justified candidate-to-candidate comparison requires loading the other candidate's "
        "scores, missing-data flags and evidence under the same application route. This "
        "context cannot identify the best candidate or infer another candidate's values.",
        "direction;delivery_scores", "limitation")
    score_lines = []
    for key in type(c.scores).model_fields:
        value = getattr(c.scores, key)
        meta = c.score_meta.get(key)
        label = "functional_score" if key == _FUNCTIONAL_SLOT else key
        text = f"{label}: {_pct(value)}"
        if key == _FUNCTIONAL_SLOT:
            text += f"; functional_score_key: {c.functional_score_key}; direction: {c.direction_label}"
        if meta:
            text += f"; tool: {meta.tool}; semantics: {meta.semantics or 'not specified'}"
            if meta.semantics == "ranking_only":
                text += "; a ranking signal, not a probability"
        score_lines.append(text + ".")
        field = "functional_score;functional_score_key" if key == _FUNCTIONAL_SLOT else f"scores.{key};score_meta.{key}"
        add(f"score_{key}", label, text + ".", field)
    add("scores", "Recorded predictor scores", "\n".join(score_lines), "scores;score_meta")
    add("scope", "Scope of evidence",
        "Predictor scores describe the functional peptide alone. No predictor was run on "
        "the assembled fusion protein; a joined sequence does not establish its activity, "
        "safety, expression or yield. Screening gates are project/tool rules rather than "
        "clinical safety evidence. The composite is exploratory: it includes indicators "
        "whose use on short peptides has not been calibrated. Missing measurements remain "
        "not assessed, never zero or a pass.",
        "score_meta;backbone_binding;assembled_sequence_available", "limitation")
    add("thermal", "Thermal-score limitation",
        f"The recorded TemStaPro score is {_pct(c.scores.thermal_stability)}. The project "
        "aggregates classifier outputs across temperature thresholds; this is not a melting "
        "temperature or a probability of tolerating a temperature interval. Its applicability "
        "to short peptides has not been calibrated, and it cannot determine fusion storage "
        "temperature or a heating protocol.",
        "scores.thermal_stability;score_meta.thermal_stability", "limitation",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC11001493/")
    add("unsupported", "Evidence needed",
        "The supplied record does not establish that requested experimental outcome or "
        "condition. A matching primary source or direct experimental validation is needed.",
        kind="limitation")
    expression = c.scaffold.expression if c.scaffold else None
    if expression and valid_source_url(expression.source_url):
        add("expression_source", "Scaffold expression source",
            f"Expression source for {c.scaffold.short_name}"
            + (f" (sequence {expression.sequence_id})" if expression.sequence_id else "")
            + f": {expression.source_url}. The source's qualifiers in the expression claim apply.",
            "scaffold.expression.source_url", "source", expression.source_url)
    if c.linker and c.linker.reference:
        reference_text = c.linker.reference
        url = valid_source_url(reference_text)
        if url is None:
            match = re.search(r"\bPMID\s*:?\s*(\d+)\b", reference_text, re.I)
            if match:
                url = f"https://pubmed.ncbi.nlm.nih.gov/{match.group(1)}/"
        add("linker_source", "Linker reference", reference_text, "linker.reference", "source", url)
    return claims


def default_claim_ids(question: str) -> list[str]:
    q = question.lower().strip()
    topics = (
        ("safety", ("safe", "safety", "tox", "hemo", "immun", "gate", "veto", "安全", "毒", "溶血", "免疫", "阈值")),
        ("assembly", ("sequence", "assembl", "backbone", "scaffold", "fuse", "序列", "组装", "骨架", "融合")),
        ("linker", ("linker", "连接肽", "接头")),
        ("expression", ("solubility", "express", "purif", "yield", "表达", "纯化", "产量", "宿主", "载体", "诱导", "菌株")),
        ("thermal", ("stability", "thermal", "温度", "耐热", "热稳定", "储存")),
        ("comparison", ("compare", "rank", "best", "peer", "composite", "比较", "排名", "综合分", "候选", "最好")),
        ("provenance", ("origin", "source", "composition", "peptide", "来源", "出处", "成分", "功能肽")),
        ("missing", ("risk", "caveat", "unassess", "missing", "limit", "风险", "缺失", "未评估", "局限", "限制")),
        ("scores", ("score", "评分", "分数")),
    )
    selected = [claim_id for claim_id, words in topics if any(word in q for word in words)]
    return ["route", *(selected or ["unsupported"])]


def render_claims(
    c: ConstructDetail, claim_ids: list[str], *, catalog: dict[str, ChatEvidence] | None = None,
) -> tuple[str, list[ChatEvidence]]:
    catalog = catalog if catalog is not None else build_claims(c)
    ids = list(dict.fromkeys(["route", *claim_ids]))
    if "expression_source" in ids:
        ids.append("expression")
    if "linker_source" in ids:
        ids.append("linker")
    if any(key in ("safety", "scores") or key.startswith("score_") for key in ids):
        ids.append("missing")
    if "expression" in ids and "expression_source" in catalog:
        ids.append("expression_source")
    if any(key in ids for key in ("assembly", "linker")):
        if "linker_source" in catalog:
            ids.append("linker_source")
        if "expression_source" in catalog:
            ids.append("expression_source")
    ids.append("scope")
    evidence = [catalog[key] for key in dict.fromkeys(ids)]
    content = "\n\n".join(item.text for item in evidence)
    if len(content) > 4000:
        raise InvalidModelOutput("selected claims exceed the answer size limit")
    return content, evidence


def template_answer(
    c: ConstructDetail, question: str, *, catalog: dict[str, ChatEvidence] | None = None,
) -> tuple[str, list[ChatEvidence]]:
    """Keep a multi-topic template answer bounded without cutting a source qualifier."""
    claims = catalog if catalog is not None else build_claims(c)
    ids = default_claim_ids(question)
    while True:
        try:
            return render_claims(c, ids, catalog=claims)
        except InvalidModelOutput:
            if len(ids) <= 2:
                return render_claims(c, ["unsupported"], catalog=claims)
            ids.pop()


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
    """Whether a model is configured at all, by settings.

    Not the same question as "did this answer come from a model". A model can be configured
    and still fail on one turn; that request then returns an explicit error. This function
    decides whether to build a model-backed generator in the first place.
    """
    from ..config import get_settings
    s = get_settings()
    return bool(s.llm_base_url and s.llm_api_key and s.llm_model and s.analysis_provider == "llm")


def build_llm_generator() -> "AnalysisGenerator | None":
    """A model-backed generator, or None when no model is reachable.

    Kept out of module import scope on purpose: the transport is a deployment concern, and the
    analysis module is imported by the tests, by the static exporter and by the service alike.
    A module that reached for an HTTP client at import time would make all three of them depend
    on a model being configured.
    """
    if not llm_configured():
        return None
    try:
        from ..config import get_settings
        from .llm import TIMEOUT_SECONDS, LlmGenerator, chat_completions_endpoint
        import json
        import urllib.request

        s = get_settings()
        endpoint = chat_completions_endpoint(s.llm_base_url or "")

        def call_model(messages: list[dict[str, str]]) -> str | None:
            if s.llm_model == "MiniMax-M3.1-Flash":
                # This model budgets reasoning and the final answer together. Its default
                # reasoning effort can exhaust a small output budget before content exists.
                options = {"reasoning_effort": "medium", "reasoning_split": True,
                           "max_completion_tokens": 8192}
                timeout = 60
            else:
                options = {"temperature": 0, "max_tokens": 1800}
                timeout = TIMEOUT_SECONDS
            payload = json.dumps({"model": s.llm_model, "messages": messages,
                                  **options}).encode("utf-8")
            request = urllib.request.Request(
                endpoint,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {s.llm_api_key}",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
            # A completed HTTP response with an unusable envelope is invalid model output,
            # rather than an unavailable provider. Network/read/non-2xx errors remain transport
            # failures and are classified by LlmGenerator.
            try:
                body = json.loads(raw.decode("utf-8"))
                return body["choices"][0]["message"]["content"]
            except (UnicodeError, ValueError, KeyError, IndexError, TypeError) as exc:
                raise InvalidModelOutput("the provider returned an invalid completion envelope") from exc

        return LlmGenerator(call_model)
    except Exception as exc:  # noqa: BLE001
        log.warning("could not build the model-backed generator: %s", exc)
        return None


def ensure_generator() -> AnalysisGenerator:
    """Register the model generator when one is configured, and report which is active.

    Idempotent in the sense that a service which already has a model-backed generator is not
    given a second one. With no model configured the check cannot short-circuit — the
    registered generator is the template, whose name is not `llm` — so the settings are read
    once more per call. That is deliberate: the alternative is a flag that would keep the
    service from noticing a model configured after startup, and what it buys back is one
    `lru_cache` hit on a `Settings` object.
    """
    global _generator
    if not llm_configured():
        _generator = TemplateGenerator()
        return _generator
    if getattr(_generator, "name", None) == PROVIDER_LLM:
        return _generator
    model_generator = build_llm_generator()
    if model_generator is not None:
        _generator = model_generator
        from ..config import get_settings
        log.info("analysis provider: model-backed (%s)", get_settings().llm_model)
    return _generator


def build_response(
    c: ConstructDetail, *, peers: list[dict] | None = None,
) -> tuple[str, list[AnalysisBlock]]:
    return PROVIDER_TEMPLATE, TemplateGenerator().blocks(c, peers=peers)


def chat(
    c: ConstructDetail,
    question: str,
    history: list[ChatMessage] | None = None,
    *,
    context_key: str | None = None,
    mode: str = "ai",
) -> ChatResponse:
    """Answer with a real model, or render records only when explicitly requested."""
    from ..config import get_settings
    from .llm import LlmGenerator

    key = context_key or make_context_key(c.id, c.safety.route_id)
    turns = [
        {"role": m.role, "content": m.content}
        for m in (history or [])
        if m.role in ("user", "assistant") and m.context_key == key and m.provider != PROVIDER_TEMPLATE
    ]
    catalog = build_claims(c)
    configured = llm_configured()
    if mode == "record":
        content, evidence = template_answer(c, question, catalog=catalog)
        provider = PROVIDER_TEMPLATE
    else:
        if not configured:
            raise LlmNotConfigured("AI chat requires a configured model endpoint, API key and model name")
        generator = get_generator()
        if not isinstance(generator, LlmGenerator):
            raise ModelUnavailable("the configured model generator is unavailable")
        content, evidence = generator.answer_with_evidence(c, question, history=turns, catalog=catalog)
        provider = PROVIDER_LLM
    message = ChatMessage(
        id=f"msg_{uuid.uuid4().hex[:12]}", role="assistant", content=content,
        timestamp=datetime.now(timezone.utc).isoformat(), actions=[], provider=provider,
        evidence=evidence, context_key=key,
    )
    return ChatResponse(
        provider=provider, construct_id=c.id, message=message,
        suggested_questions=TemplateGenerator().suggested_questions(c),
        llm_configured=configured, context_key=key, fallback_reason=None,
        model=get_settings().llm_model if configured else None,
    )
