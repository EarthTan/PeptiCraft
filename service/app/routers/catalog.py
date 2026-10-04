"""Health and reference data."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import db
from ..config import get_settings
from ..models.catalog import (
    DeliveryRoute,
    MaterialFormOption,
    PipelineView,
    ReferenceData,
    ScaffoldCategoryView,
    ToolDefinition,
)
from ..repositories import catalog as catalog_repo
from ..repositories import scaffolds as scaffolds_repo
from ..services import reference

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    """Liveness plus a database reachability check.

    Database unreachability and a failing query are reported separately, because the
    database sits on another machine behind Tailscale and the two conditions call for
    different responses: one is a network problem, the other is a query problem.

    `database.backend` names which source actually answered. When it reads `sqlite` the
    service is serving the bundled local fixture, which is seeded with four hand-made
    constructs and carries no pipeline data; `database.fallback_reason` says why it took over.
    A caller that needs to know whether it is looking at real data reads this field rather
    than inferring it from the numbers.
    """
    settings = get_settings()
    backend = db.get_backend()
    payload = {
        "ok": False,
        "database": {
            "backend": backend,
            "host": settings.igem_pg_host or "from DSN",
            "database": settings.igem_pg_db,
        },
        "analysis_provider": settings.analysis_provider,
    }
    reason = db.get_fallback_reason()
    if reason:
        payload["database"]["fallback_reason"] = reason
        payload["database"]["database"] = str(settings.sqlite_file)
        payload["database"]["note"] = (
            "Serving the local SQLite fixture, which is fixture data rather than pipeline "
            "output. It exists so the API and the interface stay workable while the remote "
            "instance is unreachable."
        )
    try:
        info = db.ping()
    except db.DatabaseUnavailable as exc:
        payload["error"] = "database_unavailable"
        payload["detail"] = str(exc)
        return payload
    except db.QueryFailed as exc:
        payload["error"] = "query_failed"
        payload["detail"] = str(exc)
        return payload

    payload["ok"] = True
    payload["database"]["server"] = (info.get("version") or "").split(" on ")[0]
    payload["database"]["now"] = info.get("ts").isoformat() if info.get("ts") else None
    return payload


def _build_reference_data() -> ReferenceData:
    counts = catalog_repo.direction_counts()
    precursors = catalog_repo.precursor_counts()
    route_map = catalog_repo.scaffold_route_map()

    # A route's scaffold list is derived from the scaffold side of the relation, so the two
    # directions cannot disagree.
    scaffolds_by_route: dict[str, list[str]] = {}
    for scaffold_id, route_ids in route_map.items():
        for route_id in route_ids:
            scaffolds_by_route.setdefault(route_id, []).append(scaffold_id)
    for ids in scaffolds_by_route.values():
        ids.sort()

    routes = [
        reference.route_with_scaffolds(route, scaffolds_by_route.get(route.id, []))
        for route in reference.ROUTES
    ]

    category_map: dict[str, list[str]] = {}
    for row in scaffolds_repo.list_scaffolds():
        if row.get("category"):
            category_map.setdefault(row["category"], []).append(row["id"])

    return ReferenceData(
        directions=reference.build_directions(counts, precursors),
        routes=routes,
        tools=[ToolDefinition(**t.model_dump()) for t in reference.TOOLS],
        evidence_levels=reference.EVIDENCE_LEVELS,
        material_forms=reference.MATERIAL_FORM_OPTIONS,
        categories=[
            ScaffoldCategoryView(
                id=cat,
                label=reference.CATEGORY_LABELS.get(cat, cat),
                scaffold_ids=sorted(ids),
            )
            for cat, ids in sorted(category_map.items())
        ],
    )


@router.get("/meta/reference", response_model=ReferenceData)
def reference_data() -> ReferenceData:
    """One call for everything that is not a construct, scaffold or linker.

    Bundled rather than split across four endpoints because the Builder needs all of it
    before it can render Step 1, and four round trips on first paint is a cost with no
    matching benefit.
    """
    return _build_reference_data()


@router.get("/meta/directions")
def directions() -> list[dict]:
    data = _build_reference_data()
    return [d.model_dump() for d in data.directions]


@router.get("/meta/routes", response_model=list[DeliveryRoute])
def routes() -> list[DeliveryRoute]:
    return _build_reference_data().routes


@router.get("/meta/tools", response_model=list[ToolDefinition])
def tools() -> list[ToolDefinition]:
    return reference.TOOLS


@router.get("/meta/pipeline", response_model=PipelineView)
def pipeline() -> PipelineView:
    return reference.PIPELINE_VIEW


@router.get("/meta/coverage")
def coverage() -> list[dict]:
    """Per-predictor coverage across the whole peptide library.

    Served so the interface can state how much of the library a predictor actually covered,
    rather than implying that a score exists for every candidate.
    """
    return catalog_repo.enrichment_coverage()
