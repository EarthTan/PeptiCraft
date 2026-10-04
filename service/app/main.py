"""PeptiCraft backend service.

Serves the frontend's established contract from the real Postgres instance, which runs on a
separate machine and is reached over its IP address. Layer boundaries are deliberate:

    routers       parameter validation, calling a service, serialising a response
    services      all thresholds, weights and business judgement
    repositories  SQL only, no thresholds and no verdicts
    models        the response contract, field names matching the frontend's types

The point of the split is that a threshold lives in exactly one place. The audit of
2026-09-17 found the same safety thresholds written out four times across the frontend, and
one of those copies disagreed with the route definitions in a way that let a construct
sitting on a tightened boundary be shown as clearing every gate.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import db
from .config import get_settings
from .routers import build, catalog, constructs, linkers, scaffolds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("pepticraft")

API_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info(
        "starting PeptiCraft service %s; database %s@%s:%s/%s; analysis provider=%s",
        API_VERSION,
        settings.igem_pg_user,
        settings.igem_pg_host or "(from DSN)",
        settings.igem_pg_port,
        settings.igem_pg_db,
        settings.analysis_provider,
    )
    if settings.analysis_provider == "llm":
        log.warning(
            "ANALYSIS_PROVIDER=llm is set but no model-backed generator is registered; the "
            "template generator remains active. See app/services/analysis.py."
        )
    db.init_pool()
    try:
        db.ping()
        log.info("database reachable (backend=%s)", db.get_backend())
    except Exception as exc:  # noqa: BLE001 - a failed probe must not stop startup
        log.warning(
            "database not reachable at startup (%s). Requests will report the failure "
            "through /api/health.", exc,
        )
    reason = db.get_fallback_reason()
    if reason:
        log.warning(
            "serving the local SQLite fixture instead of the remote instance: %s", reason
        )
    yield
    db.close_pool()
    log.info("stopped")


app = FastAPI(
    title="PeptiCraft API",
    version=API_VERSION,
    summary="Real data behind the PeptiCraft platform frontend.",
    description=(
        "Read-only over iGEM's `igem_peptides` database. Nine scores per construct are "
        "assembled from three sources: `constructs.scores` for the direction-independent "
        "keys, `peptide_enrichment` pivoted by tool for the per-peptide predictions, and "
        "computed values for the composite. Thermal stability and solubility live only in "
        "the enrichment table, which is why they appear absent if only `constructs` is read.\n\n"
        "The remote instance is reached over a tunnel and is not always up. Under the default "
        "`IGEM_DB_BACKEND=auto`, an unreachable instance is replaced by a bundled SQLite "
        "fixture holding two hand-made constructs, so the surface stays exercisable offline. "
        "`/api/health` names the backend that answered; fixture data is not pipeline data."
    ),
    lifespan=lifespan,
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(db.DatabaseUnavailable)
async def _db_unavailable(request: Request, exc: db.DatabaseUnavailable) -> JSONResponse:
    """503, not 500: the database is on another machine and unreachability is transient."""
    log.error("database unavailable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={
            "error": "database_unavailable",
            "detail": str(exc),
            "hint": (
                "The database runs on a separate host and is reached over its IP. Check that "
                "the host is up and that the VPN or network path to it is active."
            ),
        },
    )


@app.exception_handler(db.QueryFailed)
async def _query_failed(request: Request, exc: db.QueryFailed) -> JSONResponse:
    log.error("query failed: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "query_failed", "detail": str(exc)},
    )


app.include_router(catalog.router, prefix="/api")
app.include_router(build.router, prefix="/api")
app.include_router(constructs.router, prefix="/api")
app.include_router(scaffolds.router, prefix="/api")
app.include_router(linkers.router, prefix="/api")


@app.get("/", include_in_schema=False)
def index() -> dict:
    return {
        "service": "PeptiCraft API",
        "version": API_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/api/health",
    }


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
