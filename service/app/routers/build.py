"""The Builder endpoint — the one place the platform composes rather than reports.

Every other construct endpoint answers a question about a stored row. This one runs the
Builder's own step: given a route, the function directions to screen for, a scaffold and a
linker, rank the candidates and assemble each one's fused sequence. It is a pure function of
its parameters — nothing is written, and repeating a request returns the same body — which is
why it is a GET rather than a POST.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.build import BuildResult
from ..repositories import scaffolds as scaffolds_repo
from ..services import build as build_service
from ..services import linkers as linkers_service, reference

router = APIRouter(prefix="/build", tags=["build"])


def _directions(raw: list[str]) -> list[str]:
    """Normalise the direction parameters, then check them against the declared set.

    Both spellings are accepted — a repeated parameter and a comma-separated one — because a
    URL built by hand reads better with commas while a URL built by a client is easier to
    assemble by repetition. They mean the same thing, and an unknown value is rejected rather
    than ignored: a build that silently dropped a direction would return a shorter ranking
    that looks like a complete one.
    """
    values: list[str] = []
    for entry in raw:
        values.extend(part.strip() for part in entry.split(",") if part.strip())

    if not values:
        raise HTTPException(
            status_code=400,
            detail=(
                "at least one direction is required; pass `?direction=<id>` once per "
                f"direction, or several comma-separated. Expected one or more of "
                f"{', '.join(reference.DIRECTIONS_BY_ID)}"
            ),
        )

    unknown = [v for v in values if v not in reference.DIRECTIONS_BY_ID]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unknown direction(s) {', '.join(repr(v) for v in unknown)}; expected one "
                f"or more of {', '.join(reference.DIRECTIONS_BY_ID)}"
            ),
        )
    return values


@router.get("", response_model=BuildResult)
def build(
    direction: list[str] = Query(
        default_factory=list,
        description="Function direction to screen for. Repeat the parameter, or separate "
        "several with commas. At least one is required.",
    ),
    route_id: str | None = Query(
        default=None,
        description="Application route whose weighting profile and immunogenicity gate the "
        "build is computed under. Defaults to the first declared route, and the response "
        "states which route was used rather than leaving it implicit.",
    ),
    scaffold_id: str | None = Query(
        default=None,
        description="Scaffold to assemble every candidate against. When supplied, each row "
        "reports `backbone_binding=inferred`, because the scaffold-to-candidate pairing comes "
        "from this request rather than from the pipeline. When omitted, each row falls back "
        "to its own stored binding and the rows may disagree.",
    ),
    linker_id: str | None = Query(
        default=None,
        description="Linker to assemble every candidate with, named from the curated linker "
        "library or from the sample table; `source_table` on the returned `linker` says which "
        "answered. Naming one changes the fused sequence and nothing else — the candidate "
        "set, the scores and the ranking are identical to a build that names none. When "
        "omitted, each row falls back to the linker its own stored row records.",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
        description="How many ranked candidates to return. Applied after the whole candidate "
        "set has been ranked, so it slices a complete ordering rather than a page of one.",
    ),
    offset: int = Query(default=0, ge=0),
) -> BuildResult:
    """Rank the candidates and assemble their fused sequences.

    The ranking covers every stored candidate in the requested directions — the top channel
    only, since the bottom channel is the negative-control arm — ordered by composite under
    the route's weighting profile. `counts` tallies the verdicts over that whole set, so a
    caller can read the candidate set's shape without paging through it.
    """
    directions = _directions(direction)

    if route_id is None:
        route_id = reference.ROUTES[0].id
    elif route_id not in reference.ROUTES_BY_ID:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unknown application route {route_id!r}; expected one of "
                f"{', '.join(reference.ROUTES_BY_ID)}"
            ),
        )

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

    return build_service.build_candidates(
        directions=directions,
        route_id=route_id,
        scaffold_id=scaffold_id,
        linker_id=linker_id,
        limit=limit,
        offset=offset,
    )
