"""Scaffold endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.scaffold import ScaffoldDetail, ScaffoldSummary
from ..repositories import constructs as constructs_repo
from ..repositories import scaffolds as scaffolds_repo
from ..services import reference, scaffolds as service

router = APIRouter(prefix="/scaffolds", tags=["scaffolds"])


@router.get("", response_model=list[ScaffoldSummary])
def list_scaffolds(
    route_id: str | None = Query(
        default=None,
        description="Only scaffolds admitted by this application route. Derived from the "
        "scaffold side of the relation, so it cannot disagree with the route's own "
        "`scaffold_ids`.",
    ),
    category: str | None = Query(default=None, description="Stored scaffold category."),
) -> list[ScaffoldSummary]:
    if route_id is not None and route_id not in reference.ROUTES_BY_ID:
        raise HTTPException(
            status_code=400,
            detail=f"unknown application route {route_id!r}",
        )
    rows = scaffolds_repo.list_scaffolds(route_id)
    if category:
        rows = [r for r in rows if r.get("category") == category]
    return [service.to_summary(r) for r in rows]


@router.get("/{scaffold_id}", response_model=ScaffoldDetail)
def get_scaffold(scaffold_id: str) -> ScaffoldDetail:
    detail = service.load_detail(scaffold_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"scaffold {scaffold_id!r} not found")
    return detail


@router.get("/{scaffold_id}/constructs", response_model=list[dict])
def constructs_using_scaffold(
    scaffold_id: str,
    limit: int = Query(default=20, ge=1, le=200),
) -> list[dict]:
    """Constructs bound to this scaffold.

    Currently always empty, and correctly so. Every stored construct points at
    `backbone_proteins.id = 1`, a placeholder row, so no construct carries a real scaffold
    id. The endpoint exists so the relation has a defined shape once the pipeline reassembles
    against the curated library, and it returns an empty list rather than a fabricated
    association in the meantime.
    """
    if scaffolds_repo.get_scaffold(scaffold_id) is None:
        raise HTTPException(status_code=404, detail=f"scaffold {scaffold_id!r} not found")
    return []
