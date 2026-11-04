"""The Builder endpoint — the one place the platform composes rather than reports.

Every other construct endpoint answers a question about a stored row. This one runs the
Builder's own step: given a route, the function directions to screen for, a scaffold and a
linker, rank the candidates and assemble each one's fused sequence. It is a pure function of
its parameters — nothing is written, and repeating a request returns the same body — which is
why it is a GET rather than a POST.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..models.build import BuildResult
from ..repositories import scaffolds as scaffolds_repo
from ..services import build as build_service
from ..services import linkers as linkers_service, reference
from ..services import thresholds as thresholds_service

router = APIRouter(prefix="/build", tags=["build"])


def _query_list(value: Any) -> list[str]:
    """A list parameter's value, whether FastAPI resolved it or the caller did not.

    The exporter calls the router function directly rather than through FastAPI, and a
    parameter that was never resolved is still the `Query` object it was declared with. A
    parameter that arrives as neither a list nor a tuple carries no values, which is what an
    absent one means.
    """
    if isinstance(value, (list, tuple)):
        return [item for item in value]
    return []


def _query_number(value: Any) -> float | None:
    """A numeric parameter's value, or None when it carries none."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


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
    min_functional_score: list[str] = Query(
        default_factory=list,
        description="A floor on a direction's functional score, written as "
        "`direction:value` — for example `antioxidant:0.5`. Repeat the parameter or separate "
        "several with commas. The floor applies only where the direction's score is a "
        "probability; on the two ranking-only directions it is reported as not applied "
        "rather than silently ignored. A score the pipeline did not measure is not excluded "
        "by a floor, because a threshold cannot rule on what was never assessed.",
    ),
    max_allergenicity: float | None = Query(
        default=None,
        description="A ceiling on the AlgPred2 allergenicity score. The lower the value the "
        "safer the peptide is, so this is a ceiling rather than a floor.",
    ),
    min_peptide_length: int | None = Query(
        default=None,
        ge=1,
        description="The shortest peptide length to keep, in residues.",
    ),
    max_peptide_length: int | None = Query(
        default=None,
        ge=1,
        description="The longest peptide length to keep, in residues.",
    ),
    per_direction_limit: int | None = Query(
        default=None,
        ge=1,
        description="How many candidates each direction contributes, counted within that "
        "direction's own ranking. The way to hold several directions at once without one of "
        "them filling the page.",
    ),
) -> BuildResult:
    """Rank the candidates and assemble their fused sequences.

    The ranking covers every stored candidate in the requested directions — the top channel
    only, since the bottom channel is the negative-control arm — ordered by composite under
    the route's weighting profile. `counts` tallies the verdicts over that whole set, so a
    caller can read the candidate set's shape without paging through it.

    Thresholds narrow the candidate set before the ranking is sliced. They can only remove
    candidates: the twenty-million-peptide library is not reachable from here, and the
    candidate set is what the pipeline already screened.
    """
    directions = _directions(_query_list(direction))

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

    try:
        functional_floor = thresholds_service.parse_functional_floor(
            _query_list(min_functional_score)
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None

    unknown = [name for name in functional_floor if name not in reference.DIRECTIONS_BY_ID]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unknown direction(s) {', '.join(repr(name) for name in unknown)} in "
                f"`min_functional_score`; expected one or more of "
                f"{', '.join(reference.DIRECTIONS_BY_ID)}"
            ),
        )

    ceiling = _query_number(max_allergenicity)
    shortest = _query_number(min_peptide_length)
    longest = _query_number(max_peptide_length)
    cap = _query_number(per_direction_limit)

    if (
        shortest is not None
        and longest is not None
        and shortest > longest
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"`min_peptide_length` ({shortest:g}) is above "
                f"`max_peptide_length` ({longest:g}), so the range would keep nothing"
            ),
        )

    return build_service.build_candidates(
        directions=directions,
        route_id=route_id,
        scaffold_id=scaffold_id,
        linker_id=linker_id,
        limit=limit,
        offset=offset,
        thresholds=thresholds_service.Thresholds(
            functional_floor=functional_floor,
            max_allergenicity=ceiling,
            min_peptide_length=int(shortest) if shortest is not None else None,
            max_peptide_length=int(longest) if longest is not None else None,
            per_direction_limit=int(cap) if cap is not None else None,
        ),
    )
