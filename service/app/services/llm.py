"""A model-backed analysis generator, and the guardrails that keep it honest.

What this is for
----------------
`TemplateGenerator` composes prose from a construct's real fields, which makes it exact and
makes it dull: it can only say what the record already says, in the order the record says it.
A reader asking "why did this one get vetoed when the one above it did not" gets a restatement
of the gates rather than an answer, because answering that question means comparing two records
and explaining the difference, which no fixed set of paragraphs can do.

This module adds that, with one rule that shapes everything below: **the model is given the
numbers and is asked to explain them, never to produce them.** Every figure in a generated
answer is inserted from the construct's own fields, and the prompt states that the model must
not compute, estimate, infer or recall any score. A wrong safety verdict is the one failure
this project cannot afford, so the model is never in a position to produce one.

The three mechanisms that enforce it
------------------------------------
1. **The fact block.** The prompt carries a structured dump of the construct's real fields —
   the nine scores with their nulls intact, every safety gate with its threshold and verdict,
   the route's screening profile, the peptide's provenance, the assembly's binding state. The
   model sees `null` written out as `not assessed`, never as zero, because a null rendered as
   0.00 is exactly the mistake the nine-score contract exists to prevent.

2. **The instruction.** It says what the model's job is (explain and compare) and what it is
   not (no new numbers, no prediction of experimental outcome, no claim that a score is a
   probability when the stored semantics say otherwise). It also carries the same warnings the
   template carries, because those warnings are the project's own position rather than
   prompt decoration.

3. **The failure mode.** Any failure — a timeout, a refusal, an empty completion, a
   malformed one — raises `ModelUnavailable`. `analysis.chat` catches it, writes the
   template's answer and sets `provider` to `template` in the same step, so a reader is never
   left with nothing and never told the template's prose is a model's. Deciding the text and
   the label together is the point: a generator that fell back on its own would have its own
   name printed over the template's words, because the label comes from the generator's
   `name` and not from what actually answered.

Deployment note
---------------
This module runs on Cloudflare Pages Functions, not on the Python service: the deployment has
no Python runtime, and the model key must not reach the browser. The function under
`app/functions/api/constructs/[id]/chat.ts` is the HTTP surface, and it restates the rules and
the fact block in TypeScript, because a Worker cannot import a Python module. The restatement
is the one duplication in this feature and it is deliberate and visible —
`tests/test_llm.py` compares the two prompts, so a change to one that is not made to the other
fails the suite rather than shipping.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..models.analysis import AnalysisBlock
from ..models.construct import ConstructDetail
from . import reference
from .analysis import (
    PROVIDER_LLM,
    ModelUnavailable,
    TemplateGenerator,
    _route_name,
    _verdict_word,
)

log = logging.getLogger("pepticraft.llm")

# How many prior turns are sent. Enough for "and what about the other one?" to resolve, short
# enough that the fact block is not pushed out of a small context window.
HISTORY_TURNS = 6

# A generation that runs long is a generation to discard rather than to wait on: the reader is
# looking at a sidebar, and the template answer is already available.
TIMEOUT_SECONDS = 20


def chat_completions_endpoint(base_url: str) -> str:
    """The chat-completions endpoint a configured base URL points at.

    Providers differ on how much of the path they expect, so all three shapes are accepted: a
    full endpoint, a version root, and a bare host. The Pages Function applies the same rule
    (`app/functions/api/constructs/[id]/chat.ts`), and the two have to agree: one
    `LLM_BASE_URL` must reach the same endpoint whether the service or the Function answers,
    or a model that works in development would 404 in the deployment.
    """
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


# ---------------------------------------------------------------------------
# The fact block
# ---------------------------------------------------------------------------

def build_fact_block(construct: ConstructDetail) -> str:
    """Everything the model is allowed to refer to, as a structured dump.

    Written as text rather than passed as the raw JSON response for two reasons. The nulls have
    to be spelled out, because a JSON `null` reads to a model as a missing value rather than
    as "this predictor did not cover this peptide", and the difference is the whole safety
    argument. And the shape has to be flat enough that a model quoting a number is quoting a
    number that appears here, so a reader can check it against the page.
    """
    scores = construct.scores
    meta = construct.score_meta
    lines: list[str] = []

    def score_line(key: str) -> str:
        value = getattr(scores, key, None)
        label = meta.get(key)
        assessed = "assessed" if value is not None else "NOT ASSESSED"
        rendered = "not assessed" if value is None else f"{value:.6g}"
        parts = [f"- {key}: {rendered} ({assessed})"]
        if label is not None:
            parts.append(f"measured by {label.tool}")
            parts.append(f"higher is {'better' if label.higher_is_better else 'worse'}")
            if label.semantics and label.semantics != "probability":
                parts.append(f"this number is {label.semantics}, NOT a probability")
            if label.is_veto_gate:
                parts.append("a failure here eliminates the candidate")
            if label.applied_threshold is not None:
                parts.append(
                    f"threshold {label.applied_threshold.value} "
                    f"(from the {label.applied_threshold.source})"
                )
        return " | ".join(parts)

    lines.append("CONSTRUCT")
    lines.append(f"- id: {construct.id}")
    lines.append(f"- direction: {construct.direction} ({construct.direction_label})")
    lines.append(f"- channel: {construct.channel}")
    lines.append(f"- status: {construct.status}")
    lines.append(f"- peptide: {construct.peptide_sequence} ({construct.peptide_length} aa)")
    lines.append(
        f"- peptide provenance: {construct.peptide.source} "
        f"{construct.peptide.source_version}"
        + (
            f", accession {construct.peptide.source_accession}"
            if construct.peptide.source_accession
            else ""
        )
    )

    route = reference.ROUTES_BY_ID.get(construct.safety.route_id or "")
    lines.append("")
    lines.append("APPLICATION ROUTE AND ITS SCREENING PROFILE")
    if route is not None:
        lines.append(f"- route: {route.name} ({route.id})")
        lines.append(f"- barrier: {route.barrier_label}")
        lines.append(f"- immune exposure: {route.immune_exposure}")
        lines.append(
            f"- weight tiers: expression {route.screening.cpp_weight}, "
            f"solubility {route.screening.solubility_weight}, "
            f"thermal stability {route.screening.thermal_stability_weight}"
        )
    else:
        lines.append("- no route was named for this response")

    lines.append("")
    lines.append("SAFETY VERDICT")
    lines.append(f"- verdict: {construct.safety.verdict} ({_verdict_word(construct.safety.verdict)})")
    if construct.safety.immunogenicity_threshold is not None:
        lines.append(
            f"- the immunogenicity gate for this route is "
            f"{construct.safety.immunogenicity_threshold}"
        )
    for gate in construct.safety.gates:
        value = "not assessed" if gate.value is None else f"{gate.value:.6g}"
        outcome = (
            "no value, so it eliminates nothing"
            if gate.passed is None
            else ("PASS" if gate.passed else "FAIL")
        )
        failing = (
            "a value above the threshold fails"
            if not gate.higher_is_better
            else "a value below the threshold fails"
        )
        lines.append(
            f"- {gate.label}: {value} against {gate.threshold} -> {outcome} "
            f"({failing}; veto gate: {'yes' if gate.is_veto_gate else 'no'})"
        )
    if construct.safety.vetoed_by:
        lines.append(f"- stopped by: {', '.join(construct.safety.vetoed_by)}")
    if construct.safety.unassessed:
        lines.append(f"- not assessed: {', '.join(construct.safety.unassessed)}")

    lines.append("")
    lines.append("SCORES")
    for key in (
        "antioxidant", "toxicity", "hemolysis", "immunogenicity", "b_cell_epitope",
        "thermal_stability", "solubility", "cpp", "composite",
    ):
        lines.append(score_line(key))

    supplementary = construct.supplementary
    lines.append("")
    lines.append("SUPPLEMENTARY MEASUREMENTS")
    # The label is the record's own field name, so the block reads as the page does. The Pages
    # Function prints the same three, and `tests/test_llm.py` checks that.
    for key, value in (
        ("immunogenicity_ii_pct_rank", supplementary.immunogenicity_ii_pct_rank),
        ("allergenicity", supplementary.allergenicity),
        ("aggregation_a3v", supplementary.aggregation_a3v),
    ):
        rendered = "not assessed" if value is None else f"{value:.6g}"
        lines.append(f"- {key}: {rendered}")
    if supplementary.immunogenicity_ii_pct_rank is not None:
        lines.append(
            "- the MHC-II figure is a percent rank, not a probability: lower means a stronger "
            "predicted binder"
        )

    lines.append("")
    lines.append("COMPOSITE UNDER EVERY ROUTE")
    for route_id, delivery in construct.delivery_scores.items():
        name = _route_name(route_id)
        composite = "not assessed" if delivery.composite is None else f"{delivery.composite:.6g}"
        lines.append(f"- {name} ({route_id}): {composite}")

    lines.append("")
    lines.append("ASSEMBLY")
    lines.append(f"- scaffold binding: {construct.backbone_binding}")
    lines.append(f"- scaffold: {construct.backbone_name or 'none named'}")
    lines.append(f"- linker: {construct.linker_name or 'none recorded'}")
    lines.append(
        "- fused sequence: "
        + ("available" if construct.assembled_sequence_available else "not available")
    )
    if construct.full_sequence:
        lines.append(f"- fused length: {len(construct.full_sequence)} aa")
    if construct.status == "WIP":
        lines.append("- this construct's direction has not been signed off")

    return "\n".join(lines)


SYSTEM_PROMPT = """\
You are the analysis assistant for PeptiCraft, a platform that screens short peptide \
candidates for functional proteins used in topical and injectable biomaterials.

A reader is looking at one construct and has asked you a question about it. Answer from the \
fact block you have been given, which is the construct's own record.

Rules, in order of importance:

1. Never produce a number that is not in the fact block. Do not compute a score, convert a \
score to a percentage, average two values, estimate a molecular weight, or recall a figure \
from training. If the reader asks for something the block does not contain, say the record \
does not contain it.

2. "Not assessed" means the predictor did not cover this peptide. It is not a zero and not a \
pass. A construct can clear every gate that was assessed while one of them was never \
measured, and that is a different statement from clearing everything.

3. Some scores are marked as ranking-only. They order candidates; they are not probabilities \
and must never be described as confidence or likelihood.

4. Scores describe the functional peptide alone. The scaffold and the linker change the \
concatenation; no predictor was run on the fusion protein. Do not describe the assembled \
protein as characterised.

5. An assembled sequence is a reproduction of three real sequences joined together. When the \
scaffold was named by the reader rather than recorded against the construct, say that the \
pairing is a reconstruction.

6. Where a score sits near its threshold, say so plainly and give both numbers. Do not \
soften a borderline result into a pass or a fail.

Write in plain prose, two short paragraphs at most. No bullet lists, no headings, no \
markdown. Be direct: the reader has the numbers on the screen and wants the reading of them, \
not a restatement. British or American spelling are both acceptable; be consistent within an \
answer.
"""


def build_messages(
    construct: ConstructDetail, question: str, history: list[dict[str, Any]] | None = None
) -> list[dict[str, str]]:
    """The message list for one request: system, recent turns, then the question.

    The fact block is attached to the question rather than to the system prompt, so it is the
    most recent thing the model read when it answers — which matters when the history is long
    enough to have pushed anything else out of attention.
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    turns = [
        turn
        for turn in (history or [])
        if turn.get("role") in ("user", "assistant")
        and isinstance(turn.get("content"), str)
        and turn["content"].strip()
    ]
    # A client that sends the question it is asking as the last turn of the history would have
    # the model read it twice, and a model that reads one question twice tends to answer the
    # first copy. The current question is appended below, so the duplicate is dropped here
    # rather than relied on not to arrive.
    if turns and turns[-1]["role"] == "user" and turns[-1]["content"].strip() == question.strip():
        turns = turns[:-1]

    for turn in turns[-HISTORY_TURNS:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({
        "role": "user",
        "content": f"FACT BLOCK\n{build_fact_block(construct)}\n\nQUESTION\n{question}",
    })
    return messages


# ---------------------------------------------------------------------------
# The generator
# ---------------------------------------------------------------------------

class LlmGenerator:
    """A generator that answers with a model, and says so when it cannot.

    It does not fall back to the template itself. The caller labels an answer from the
    generator's `name`, not from what actually produced the text, so a generator that quietly
    substituted the template's prose would hand back template prose under a model's label —
    exactly the confusion this feature has to avoid. A failure therefore raises
    `ModelUnavailable`, and `analysis.chat` writes the template's answer and the `template`
    label together.
    """

    name = PROVIDER_LLM

    def __init__(
        self,
        call_model: Any,
        template: TemplateGenerator | None = None,
    ) -> None:
        # `call_model(messages) -> str | None`. Injected rather than imported so the transport
        # is a deployment concern: the service would pass a synchronous HTTP call and the Pages
        # Function passes `fetch`, and neither knows about the other.
        self._call_model = call_model
        # Still held for `blocks` and `suggested_questions`, which stay on the template.
        self._template = template or TemplateGenerator()

    def answer(
        self,
        construct: ConstructDetail,
        question: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """The model's answer, or `ModelUnavailable`.

        `history` reaches the model here; without it a question like "and the one above it?"
        has nothing to resolve against.
        """
        try:
            generated = self._call_model(build_messages(construct, question, history))
        except Exception as exc:  # noqa: BLE001 - any transport failure is the same outcome
            raise ModelUnavailable(f"the model call failed: {exc}") from exc

        if not generated or not generated.strip():
            raise ModelUnavailable("the model returned nothing usable")

        return generated.strip()

    def blocks(self, construct: ConstructDetail) -> list[AnalysisBlock]:
        """The six standing analyses stay on the template.

        These are not questions; they are the fixed set of things worth saying about every
        construct, and each one is a rendering of the record. A model would phrase them
        differently on every load, which would make two readers of the same construct see
        different claims about it, and would occasionally phrase one of them wrongly. The
        generated text is for the questions the template cannot anticipate.
        """
        return self._template.blocks(construct)

    def suggested_questions(self, construct: ConstructDetail) -> list[str]:
        return self._template.suggested_questions(construct)


def summarise_fact_block(construct: ConstructDetail) -> dict[str, Any]:
    """The fact block as a dict, for a caller that wants it structured rather than as text.

    Exported because the Pages Function logs it on a failed generation, and a log line that
    cannot be read against the page is not worth keeping.
    """
    return {
        "construct_id": construct.id,
        "verdict": construct.safety.verdict,
        "route_id": construct.safety.route_id,
        "composite": construct.scores.composite,
        "unassessed": construct.safety.unassessed,
        "text": build_fact_block(construct),
    }


__all__ = [
    "HISTORY_TURNS",
    "PROVIDER_LLM",
    "SYSTEM_PROMPT",
    "TIMEOUT_SECONDS",
    "LlmGenerator",
    "ModelUnavailable",
    "build_fact_block",
    "build_messages",
    "chat_completions_endpoint",
    "summarise_fact_block",
]