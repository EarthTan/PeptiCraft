"""Analysis and chat models.

The six analysis block kinds match the frontend's `AiBlock.type` union so the existing
component tree keeps working. What changes is where the text comes from: it is rendered per
construct from that construct's real scores, thresholds and route profile rather than being
a fixed string, which is what let the old copy keep quoting a 32-linker library, 1,760 Da
and "8 rounds of screening" long after none of those were true.

`provider` on each response says which generator produced the text. That field exists so a
later LLM-backed generator can be introduced without the frontend needing to know, and so
that a reviewer can tell deterministic prose from model output.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# How much of a conversation is kept. The interface sends every turn it has, and only the last
# few are ever read, so the rest is dropped rather than carried.
MAX_HISTORY_TURNS = 50


class ExpressionPlan(BaseModel):
    """Legacy expression-plan shape retained for existing stored exports.

    New analysis blocks leave this null: scaffold evidence does not establish induction or
    purification conditions for a newly assembled fusion, so unknown parameters are not filled
    by composition-based rules.
    """

    host: str
    strain: str
    vector: str
    tag: str
    induction: str
    temperature_c: int
    duration_h: str
    purification: str
    tier: str = Field(
        default="standard",
        description="`standard` / `solubility-rescue` / `tight-control` / `secretion`. "
        "Names which rule in the generator fired, so a reader can tell a default route from "
        "one chosen to work around a predicted property.",
    )


class AnalysisBlock(BaseModel):
    id: str
    type: str = Field(
        description="`safety` / `peptide_origin` / `linker_rationale` / "
        "`expression_strategy` / `comparison` / `risk`."
    )
    title: str
    icon: str
    content: str
    collapsed: bool = False
    plan: ExpressionPlan | None = Field(
        default=None,
        description="Populated only by `expression_strategy`. The recommendation as fields, "
        "so the interface can render it without parsing the prose.",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Field paths the prose is derived from, such as "
        "`scores.toxicity` or `route.wound-dressing.screening.immunogenicity_threshold`. "
        "Every number in the text traces back to one of these.",
    )


class AnalysisResponse(BaseModel):
    construct_id: str
    provider: str
    route_id: str | None = None
    blocks: list[AnalysisBlock]


class ChatAction(BaseModel):
    label: str
    action: str
    variant: str = "default"


class ChatEvidence(BaseModel):
    """A rendered claim and the exact field or source that supports it."""

    id: str
    label: str
    text: str
    kind: Literal["record", "source", "limitation"]
    field: str | None = None
    url: str | None = None


class ChatMessage(BaseModel):
    id: str
    role: str = Field(description="`user` or `assistant`.")
    # Both generated answers and any history sent back by a client are bounded.
    content: str = Field(max_length=4000)
    timestamp: str
    actions: list[ChatAction] = Field(default_factory=list)
    provider: Literal["llm", "template"] | None = None
    evidence: list[ChatEvidence] = Field(default_factory=list)
    context_key: str | None = None


class ChatRequest(BaseModel):
    """A question about one construct, in the context of one application route.

    Not a free-standing conversation: the service is stateless and idempotent, and the
    answer is derived from the construct's own record. `route_id` matters because the
    immunogenicity gate and the composite depend on it, so the same question can have a
    different correct answer under a different route.
    """

    construct_id: str
    message: str = Field(min_length=1, max_length=2000)
    mode: Literal["ai", "record"] = "ai"
    route_id: str | None = None
    scaffold_id: str | None = None
    linker_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)

    @field_validator("history", mode="before")
    @classmethod
    def _keep_the_recent_turns(cls, value: object) -> object:
        """Keep the tail of the conversation instead of rejecting a long one.

        The interface sends its whole transcript, so a reader who has asked twenty-five
        questions would otherwise start getting an error they could do nothing about. Only the
        last few turns reach the model, so dropping the head changes no answer, and the bound
        is what keeps one request from carrying an unbounded amount of text.
        """
        if isinstance(value, list) and len(value) > MAX_HISTORY_TURNS:
            return value[-MAX_HISTORY_TURNS:]
        return value


class ChatResponse(BaseModel):
    provider: str
    construct_id: str
    message: ChatMessage
    suggested_questions: list[str] = Field(default_factory=list)
    llm_configured: bool = Field(
        default=False,
        description="Whether the model endpoint, key and model name are configured. "
        "The per-message provider says whether this particular answer used the model.",
    )
    context_key: str = ""
    fallback_reason: Literal["not_configured", "model_unavailable", "invalid_output"] | None = None
    model: str | None = None
