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

from pydantic import BaseModel, Field


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


class ChatMessage(BaseModel):
    id: str
    role: str = Field(description="`user` or `assistant`.")
    content: str
    timestamp: str
    actions: list[ChatAction] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """A question about one construct, in the context of one application route.

    Not a free-standing conversation: the service is stateless and idempotent, and the
    answer is derived from the construct's own record. `route_id` matters because the
    immunogenicity gate and the composite depend on it, so the same question can have a
    different correct answer under a different route.
    """

    construct_id: str
    message: str = Field(min_length=1, max_length=2000)
    route_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    provider: str
    construct_id: str
    message: ChatMessage
    suggested_questions: list[str] = Field(default_factory=list)
    llm_configured: bool = Field(
        default=False,
        description="False while the active generator is the deterministic template. "
        "The chat surface uses it to avoid presenting template output as model output.",
    )
