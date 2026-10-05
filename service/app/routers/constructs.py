"""Construct endpoints — the Library, Builder and Results pages all read from here."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..models.analysis import AnalysisResponse, ChatRequest, ChatResponse
from ..models.construct import ConstructDetail, ConstructPage, ConstructSummary
from ..models.scaffold import ScaffoldSummary
from ..repositories import constructs as repo
from ..repositories import enrichment
from ..repositories import scaffolds as scaffolds_repo
from ..services import analysis as analysis_service
from ..services import constructs as service
from ..services import linkers as linkers_service, reference

router = APIRouter(prefix="/constructs", tags=["constructs"])

_PUBLIC_ID = re.compile(r"^con_(\d+)$")


def _db_id(public_id: str) -> int:
    m = _PUBLIC_ID.match(public_id)
    if not m:
        raise HTTPException(
            status_code=400,
            detail=f"construct id must look like `con_0001`, received {public_id!r}",
        )
    return int(m.group(1))


def _load(public_id: str) -> dict:
    row = repo.get_construct(_db_id(public_id))
    if row is None:
        raise HTTPException(status_code=404, detail=f"construct {public_id} not found")
    return row


def _validate_route(route_id: str | None) -> None:
    if route_id is not None and route_id not in reference.ROUTES_BY_ID:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unknown application route {route_id!r}; expected one of "
                f"{', '.join(reference.ROUTES_BY_ID)}"
            ),
        )


@router.get("", response_model=ConstructPage)
def list_constructs(
    direction: str | None = Query(default=None, description="Stored direction value."),
    channel: Literal["top", "bottom"] | None = Query(default=None),
    status: Literal["passed", "failed_safety", "failed_score", "WIP"] | None = Query(default=None),
    route_id: str | None = Query(
        default=None,
        description="Application route whose profile the composite is computed under. "
        "Affects the composite and the safety verdict, not the filtering.",
    ),
    search: str | None = Query(
        default=None,
        max_length=200,
        description="Substring match against the peptide's sequence, source, accession and "
        "source version. Matching is case-insensitive and literal: `%` and `_` in the term "
        "match those characters rather than acting as wildcards.",
    ),
    order: Literal["rank", "peptide_length", "peptide_id"] = Query(
        default="rank",
        description="Row order. `rank` follows the pipeline's own ordering within each "
        "direction and channel; the other two are for locating a peptide rather than for "
        "reading the screening result.",
    ),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConstructPage:
    """Paginated construct list.

    `channel=bottom` returns the negative-control arm. Those rows are real and carry real
    scores, but they exist to give a comparison baseline rather than to be candidates, so a
    caller that wants candidates should filter on `channel=top`.
    """
    _validate_route(route_id)
    if direction is not None and direction not in reference.DIRECTIONS_BY_ID:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unknown direction {direction!r}; expected one of "
                f"{', '.join(reference.DIRECTIONS_BY_ID)}"
            ),
        )

    rows, total = repo.list_constructs(
        direction=direction, channel=channel, status=status,
        search=search.strip() if search else None,
        order=order,
        limit=limit, offset=offset,
    )
    enriched = service.load_enrichment(rows)
    items = service.build_summaries(rows, enriched, route_id=route_id)
    return ConstructPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{construct_id}", response_model=ConstructDetail)
def get_construct(
    construct_id: str,
    route_id: str | None = Query(
        default=None,
        description="Application route whose immunogenicity gate and weighting profile the "
        "response is computed under. Defaults to the first declared route.",
    ),
    scaffold_id: str | None = Query(
        default=None,
        description="Name a scaffold to assemble the fused sequence with. Omit to receive "
        "the stored placeholder binding with no fused sequence. When supplied, the response "
        "reports `backbone_binding=inferred`, because the assignment comes from the request "
        "rather than from the pipeline.",
    ),
    linker_id: str | None = Query(
        default=None,
        description="Name a linker to assemble the fused sequence with, overriding the one "
        "this construct records. The Builder's result cards link here with the linker they "
        "used, so that the sequence shown is the sequence the build produced. Omit to keep "
        "the recorded linker; `linker_note` on the response says which of the two happened.",
    ),
) -> ConstructDetail:
    _validate_route(route_id)
    row = _load(construct_id)
    if scaffold_id is not None and scaffolds_repo.get_scaffold(scaffold_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"scaffold {scaffold_id!r} not found",
        )
    if linker_id is not None and linkers_service.view_for(linker_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"linker {linker_id!r} not found",
        )
    enriched = enrichment.scores_for_peptides([row["peptide_id"]])
    return service.build_detail(
        row, enriched.get(row["peptide_id"], {}),
        route_id=route_id, scaffold_id=scaffold_id, linker_id=linker_id,
    )


@router.get("/{construct_id}/scaffolds", response_model=list[ScaffoldSummary])
def scaffold_candidates(construct_id: str) -> list[ScaffoldSummary]:
    """Scaffolds that could be used to assemble this construct.

    Narrowed by the routes the stored scenario hints at, and returned as options. Nothing is
    applied silently: the service never photographs a scaffold onto a construct and presents
    it as the construct's own.
    """
    row = _load(construct_id)
    return service.scaffold_candidates(row)


@router.get("/{construct_id}/peptide")
def peptide_detail(construct_id: str) -> dict:
    """Every predictor's output for this construct's peptide.

    Includes the raw `details` JSONB each tool wrote, which carries the model name, the
    threshold and any sub-scores. This is the endpoint that makes the nine assembled scores
    checkable against their sources.
    """
    row = _load(construct_id)
    return {
        "construct_id": construct_id,
        "peptide": {
            "id": row["peptide_id"],
            "sequence": row["peptide_sequence"],
            "length": row["peptide_length"],
            "source": row["peptide_source"],
            "source_version": str(row["peptide_source_version"]),
            "source_accession": row.get("peptide_source_accession"),
            "seq_md5": (row.get("peptide_md5") or "").strip(),
        },
        "tools": enrichment.details_for_peptide(row["peptide_id"]),
        "stored_construct_scores": repo.scores_of(row),
        "stored_delivery_scores": repo.delivery_scores_of(row),
    }


@router.get("/{construct_id}/analysis", response_model=AnalysisResponse)
def analysis(
    construct_id: str,
    route_id: str | None = Query(default=None),
) -> AnalysisResponse:
    _validate_route(route_id)
    row = _load(construct_id)
    enriched = enrichment.scores_for_peptides([row["peptide_id"]])
    detail = service.build_detail(row, enriched.get(row["peptide_id"], {}), route_id=route_id)
    provider, blocks = analysis_service.build_response(detail)
    return AnalysisResponse(
        construct_id=construct_id, provider=provider, route_id=route_id, blocks=blocks,
    )


@router.post("/{construct_id}/chat", response_model=ChatResponse)
def chat(construct_id: str, request: ChatRequest) -> ChatResponse:
    """Answer a question about one construct.

    Stateless and idempotent: the answer is derived from the construct's record, so the same
    question under the same route always returns the same text. `history` is accepted and
    currently ignored; it exists so a model-backed generator can be dropped in without a
    request-shape change.
    """
    route_id = request.route_id
    _validate_route(route_id)
    row = _load(construct_id)
    enriched = enrichment.scores_for_peptides([row["peptide_id"]])
    detail = service.build_detail(row, enriched.get(row["peptide_id"], {}), route_id=route_id)
    return analysis_service.chat(detail, request.message)
