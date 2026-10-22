"""Export every API response to static JSON, so the platform can be hosted without a server.

    python scripts/export_static.py --out ../app/public/data
    python scripts/export_static.py --out ../app/public/data \\
        --backend sqlite --allow-fixture --dry-run

Why this exists
---------------
The database lives on a workstation that is not always reachable, and the Python service
cannot be deployed to Cloudflare Pages because `psycopg` ships a native binary. The platform
is going to be served as static files from an edge host, so the responses have to exist as
files.

Why it calls the service layer rather than the SQL layer
-------------------------------------------------------
Every threshold, weight and verdict in this platform lives in `services/`, and the audit of
2026-09-17 found the same safety thresholds written out four times across the frontend, with
one copy disagreeing with the route definitions. An exporter that reimplemented the scoring to
walk the tables directly would introduce the fifth copy and the same class of bug.

So this script calls the same functions the routers call, through the same Pydantic models,
and writes what they return. A static file and a live response are then the same bytes, which
is the only property that makes the static build trustworthy enough to ship.

What gets written
-----------------
    meta.json                  reference data, directions, routes, tools, pipeline
    health.json                a liveness record that names the export, not a database
    scaffolds.json             every scaffold summary
    scaffolds/<id>.json        one scaffold detail each
    scaffolds/route/<id>.json  the scaffolds one route admits
    linkers.json               the curated library
    linkers/all.json           both linker tables
    linkers/<id>.json          one linker detail each
    constructs.json            every construct summary, one flat list
    constructs/<id>.json       one construct detail, plus authoritative route_contexts
    constructs/<id>/scaffolds.json
    constructs/<id>/analysis.json       the six standing prose blocks
    constructs/<id>/analysis_by_route.json  complete analyses keyed by application route
    composites.json            the composite per construct per route
    verdicts.json              the safety verdict per construct per route
    assembly.json              which parts each route admits, plus one worked example
    peptide_details.json       each construct's raw per-predictor output
    builds/<route>/<directions>.json    the Builder's ranking, per route and per direction set
                                        (every non-empty subset of the four; the full set keeps
                                        the shorter name all.json as well)

Composites are route-dependent and safety verdicts are route-dependent, so both are computed
once per route at export time rather than in the browser. Recomputing them client-side would
mean a second implementation of the weighting profile in TypeScript, which is exactly the
duplication this project has been removing.

An export replaces the output directory rather than merging into it. The static layer turns a
request path into a file path, so anything an earlier export left behind is still reachable;
`_prune_previous_export` removes it first, and only when the directory already carries a
`manifest.json` of ours.

The chat endpoint is not exported: it is the one endpoint that takes a question, and it is
served by the model proxy at request time instead.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from datetime import date, datetime
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from typing import Any
from uuid import UUID

# Run from anywhere: make `service/` importable as the package root the app expects.
_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICE_ROOT))

from app import db  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.models.analysis import AnalysisResponse  # noqa: E402
from app.repositories import constructs as constructs_repo  # noqa: E402
from app.repositories import enrichment  # noqa: E402
from app.routers import build as build_router  # noqa: E402
from app.routers import catalog as catalog_router  # noqa: E402
from app.routers import linkers as linkers_router  # noqa: E402
from app.routers import scaffolds as scaffolds_router  # noqa: E402
from app.services import analysis as analysis_service  # noqa: E402
from app.services import build as build_service  # noqa: E402
from app.services import constructs as construct_service  # noqa: E402
from app.services import reference  # noqa: E402
from app.services import scoring  # noqa: E402

log = logging.getLogger("pepticraft.export")

# Written into every file so the interface can say what it is looking at. A static build that
# does not date itself reads as current forever.
SCHEMA_VERSION = 1


def _dump(model: Any) -> Any:
    """A Pydantic model, list or plain value as plain JSON-able data.

    Recurses into containers because the analysis generator returns a `(provider, blocks)`
    tuple rather than a single model, and a bare `model_dump` on the tuple would leave the
    blocks inside it as model objects.
    """
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if isinstance(model, dict):
        return {k: _dump(v) for k, v in model.items()}
    if isinstance(model, (list, tuple)):
        return [_dump(m) for m in model]
    return model


def _json_default(value: Any) -> Any:
    """Serialise the few non-JSON types a repository can hand back.

    Pydantic models are dumped with `mode="json"` and arrive clean, but a couple of
    endpoints return repository rows as plain dicts, and those carry whatever the driver
    produced: `psycopg` returns `numeric` as `Decimal` and timestamps as `datetime`, where
    SQLite returns floats and strings. `v_peptide_enrichment_coverage.coverage_pct` is
    `numeric`, which is what made the first PostgreSQL-backed export fail while every
    fixture-backed one had passed.
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )


class Exporter:
    def __init__(self, out_dir: Path, *, dry_run: bool = False) -> None:
        self.out = out_dir
        self.dry_run = dry_run
        self.files = 0
        self.bytes = 0
        # Relative path -> byte size, filled as files are written and published as
        # `manifest.json` at the end. The frontend reads it to decide whether an export exists
        # at all, which is what keeps a deployment with no data from looking like one that
        # merely failed to load.
        self.written: dict[str, int] = {}

    def write(self, relative: str, payload: Any) -> None:
        """Write one JSON file. Directories are created on the way, and a dry run only counts.
        """
        self.files += 1
        rendered = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), default=_json_default,
        )
        encoded = len(rendered.encode("utf-8"))
        self.bytes += encoded
        self.written[relative] = encoded
        if self.dry_run:
            return
        target = self.out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")

    def publish_manifest(self) -> None:
        """Write the index the frontend probes.

        `exported_at` is what makes a static build honest about being a snapshot: a deployment
        that reads files will never update on its own, so the date has to be visible somewhere
        a reader can reach rather than only in a build log.
        """
        self.write("manifest.json", {
            "schema_version": SCHEMA_VERSION,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_backend": db.get_backend(),
            "files": dict(sorted(self.written.items())),
        })

    # -- reference ------------------------------------------------------------

    def meta(self) -> None:
        # The router's own bundle, so the split endpoints below cannot disagree with it.
        bundle = catalog_router.reference_data().model_dump(mode="json")
        self.write("meta.json", {"schema_version": SCHEMA_VERSION, **bundle})
        self.write("meta/directions.json", bundle["directions"])
        self.write("meta/routes.json", bundle["routes"])
        self.write("meta/tools.json", bundle["tools"])
        self.write("meta/pipeline.json", catalog_router.pipeline().model_dump(mode="json"))
        self.write("meta/coverage.json", catalog_router.coverage())

    def health(self) -> None:
        """A liveness record describing the export rather than a database.

        A static build has no database to be unreachable, so `backend` reads `static` and `ok`
        is true by construction. That alone cannot tell the interface whether the numbers are
        pipeline output or the sample fixture, so the export also records `source_backend`.
        The banner reads that field: an export made from the fixture announces itself on every
        page, and one made from the real instance stays quiet. Without it, a fixture-derived
        build would be indistinguishable from a real one at runtime — the same silence the
        banner exists to prevent.
        """
        source = db.get_backend()
        self.write("health.json", {
            "ok": True,
            "static": True,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "schema_version": SCHEMA_VERSION,
            "source_backend": source,
            "database": {
                "backend": "static",
                "host": None,
                "database": None,
                "note": (
                    "This deployment reads a static export rather than a database. The files "
                    "were produced from the pipeline's own database by scripts/export_static.py "
                    "and are not updated at runtime."
                ),
            },
            "analysis_provider": get_settings().analysis_provider,
        })

    # -- scaffolds and linkers ------------------------------------------------

    def scaffolds(self) -> None:
        summaries = scaffolds_router.list_scaffolds(route_id=None, category=None)
        self.write("scaffolds.json", _dump(summaries))
        for summary in summaries:
            detail = scaffolds_router.get_scaffold(summary.id)
            self.write(f"scaffolds/{_safe(summary.id)}.json", _dump(detail))
            # The per-route lists are derived from the scaffold side of the relation, so the
            # Builder's step one can narrow without the interface restating the mapping.
            for route in reference.ROUTES:
                self.write(
                    f"scaffolds/route/{_safe(route.id)}.json",
                    _dump(scaffolds_router.list_scaffolds(route_id=route.id, category=None)),
                )

    def linkers(self) -> None:
        """Both linker tables, exported as two lists rather than merged.

        `source_table` on each row says which table answered, and keeping the split preserves
        the fact that a construct's recorded linker was attached by the assembly script rather
        than chosen. The frontend reads the curated list for the Builder and may read the
        sample rows when it needs to explain where a stored linker came from.
        """
        curated = linkers_router.list_linkers(include_placeholder=False)
        both = linkers_router.list_linkers(include_placeholder=True)
        self.write("linkers.json", _dump(curated))
        self.write("linkers/all.json", _dump(both))
        for view in both:
            detail = linkers_router.get_linker(view.id)
            self.write(f"linkers/{_safe(view.id)}.json", _dump(detail))

    # -- constructs -----------------------------------------------------------

    def constructs(self) -> None:
        """Every construct, as one summary list and one detail file each.

        The detail is built with no scaffold and no linker named, so what it carries is what
        the construct's own record supports. The Builder's request-time assembly is exported
        separately under `builds/`, because that pairing belongs to the caller's choice rather
        than to the record.
        """
        rows, total = constructs_repo.list_constructs(limit=100000, offset=0)
        log.info("exporting %d constructs", total)
        enriched = construct_service.load_enrichment(rows)
        summaries = construct_service.build_summaries(rows, enriched, route_id=None)
        self.write("constructs.json", {
            "schema_version": SCHEMA_VERSION,
            "total": total,
            "items": [s.model_dump(mode="json") for s in summaries],
        })

        # This cache belongs to one export only. The running API still reads live peer data;
        # repeated constructs in a direction reuse the same route-specific export snapshot.
        peers_by_context: dict[tuple[str, str], list[dict]] = {}

        for row in rows:
            public_id = construct_service.public_id(row["id"])
            details_by_route = {
                route.id: construct_service.build_detail(
                    row, enriched.get(row["peptide_id"], {}), route_id=route.id,
                )
                for route in reference.ROUTES
            }
            default_route_id = reference.ROUTES[0].id
            exported_detail = _dump(details_by_route[default_route_id])
            # Export-only metadata: leave the API model unchanged while giving the browser
            # the exact safety gates, thresholds and composite the API computed per route.
            exported_detail["route_contexts"] = {
                route_id: {"composite": detail.composite, "safety": _dump(detail.safety)}
                for route_id, detail in details_by_route.items()
            }
            self.write(f"constructs/{public_id}.json", exported_detail)
            candidates = construct_service.scaffold_candidates(row)
            self.write(
                f"constructs/{public_id}/scaffolds.json",
                [_dump(c) for c in candidates],
            )
            analyses_by_route: dict[str, Any] = {}
            for route_id, detail in details_by_route.items():
                context = (detail.direction, route_id)
                if context not in peers_by_context:
                    peers_by_context[context] = analysis_service._direction_peers(
                        detail.direction, limit=5, route_id=route_id,
                    )
                provider, blocks = analysis_service.build_response(
                    detail, peers=peers_by_context[context],
                )
                analyses_by_route[route_id] = _dump(AnalysisResponse(
                    construct_id=public_id, provider=provider,
                    route_id=route_id, blocks=blocks,
                ))
            self.write(
                f"constructs/{public_id}/analysis.json",
                analyses_by_route[default_route_id],
            )
            self.write(
                f"constructs/{public_id}/analysis_by_route.json", analyses_by_route,
            )

    def composites_by_route(self) -> None:
        """The composite under every route, per construct.

        The detail file already carries `delivery_scores` keyed by route id, so this is the
        same numbers in a form the list page can sort and filter without opening 496 files.
        """
        rows, _ = constructs_repo.list_constructs(limit=100000, offset=0)
        enriched = construct_service.load_enrichment(rows)
        table: dict[str, dict[str, float | None]] = {}
        verdicts: dict[str, dict[str, str]] = {}
        for row in rows:
            public_id = construct_service.public_id(row["id"])
            computed = construct_service.compute(row, enriched.get(row["peptide_id"], {}), None)
            table[public_id] = {
                route.id: computed.delivery[route.id].composite
                for route in reference.ROUTES
                if route.id in computed.delivery
            }
            # The safety verdict is per route as well: the immunogenicity gate is the route's
            # threshold, so a construct can clear one application path and be vetoed on another.
            verdicts[public_id] = {}
            for route in reference.ROUTES:
                v = scoring.evaluate_safety(computed.scores, computed.supplementary, route.id)
                verdicts[public_id][route.id] = v.verdict
        self.write("composites.json", table)
        self.write("verdicts.json", verdicts)

    # -- builds ---------------------------------------------------------------

    def ranking(self, *, direction: list[str], route_id: str) -> Any:
        """One ranking, whole.

        Paged rather than requested in a single call, because the service slices what it
        returns and a single request with a fixed limit would write a file that holds the head
        of the ranking while `total` still reported the whole candidate set — a page past the
        cut would come back empty on a site that said there was more. The loop is bounded by
        the service's own candidate ceiling, which rejects a direction set that is too large
        to rank rather than truncating it.
        """
        page_size = 500
        first = build_router.build(
            direction=direction, route_id=route_id,
            scaffold_id=None, linker_id=None, limit=page_size, offset=0,
        )
        if first.total <= page_size or not first.items:
            return first
        items = list(first.items)
        while len(items) < first.total:
            page = build_router.build(
                direction=direction, route_id=route_id,
                scaffold_id=None, linker_id=None, limit=page_size, offset=len(items),
            )
            if not page.items:
                break
            items.extend(page.items)
        return first.model_copy(update={"items": items, "limit": len(items), "offset": 0})

    def builds(self) -> None:
        """Every (route, direction-set) ranking the Builder can ask for.

        Every non-empty subset of the four directions, per route: fifteen combinations rather
        than the four single directions and the full set. The extra files are the price of not
        putting the ordering rule in the browser. The service ranks a set as a set — a
        candidate's composite is a weighted mean over the direction set, through the route's own
        weights — so a two-direction request cannot be answered by slicing the four-direction
        ranking, and merging the single-direction files in the interface would mean a second
        implementation of the ordering. A file per subset keeps the order the service's own.

        Names are the member ids sorted and joined with `+`, so a set has one name whatever
        order it was asked in; the interface builds the same key the same way. The full set also
        keeps the name `all.json`, which is shorter than its member list and is what earlier
        exports and their references used.
        """
        directions = list(reference.DIRECTIONS_BY_ID)
        for route in reference.ROUTES:
            full = None
            for size in range(1, len(directions) + 1):
                for subset in combinations(directions, size):
                    names = list(subset)
                    result = self.ranking(direction=names, route_id=route.id)
                    self.write(
                        f"builds/{_safe(route.id)}/{_safe(_directions_key(names))}.json",
                        _dump(result),
                    )
                    if size == len(directions):
                        full = result
            if full is not None:
                self.write(f"builds/{_safe(route.id)}/all.json", _dump(full))
                log.info(
                    "builds for %s: %d combinations, %d candidates in the full set",
                    route.id, 2 ** len(directions) - 1, full.total,
                )

    def assembly_recipes(self) -> None:
        """The assembly recipe for every scaffold and linker pairing, per route.

        This replaces what would otherwise be one fully-assembled build per pairing. With
        eight scaffolds and fifteen linkers across five routes, exporting each pairing as a
        whole ranked result would be six hundred files each carrying every candidate's fused
        sequence — megabytes of near-duplicate text, since the fused sequence of a candidate
        under a given pairing is the concatenation of three fixed strings and its peptide.

        What actually varies with the pairing is the three parts, and they are already
        exported: `scaffolds/<id>.json` carries the scaffold's sequence, `linkers/<id>.json`
        carries the linker's, and the candidate's peptide sequence is on the candidate. So
        what is written here is the join: which parts each route admits, and the provenance
        notes that say the pairing is the caller's reconstruction rather than a pipeline
        result. The interface concatenates the three and reports the fused length.

        That does move one step — the concatenation — out of the service. It is the one step
        that has no threshold, no weight and no verdict in it: it is string joining over
        sequences that are all present as data, and a mistake in it shows as a visibly wrong
        residue string rather than as a wrong safety verdict.
        """
        recipes: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "routes": {}}
        directions = list(reference.DIRECTIONS_BY_ID)
        for route in reference.ROUTES:
            scaffolds = scaffolds_router.list_scaffolds(route_id=route.id, category=None)
            linkers = linkers_router.list_linkers(include_placeholder=False)
            recipes["routes"][route.id] = {
                "scaffolds": [s.id for s in scaffolds],
                "linkers": [linker.id for linker in linkers],
                # The notes the assembled response carries, written once per route rather than
                # copied into every pairing.
                "binding_note": construct_service.INFERRED_BINDING_NOTE,
                "linker_note": build_service.CHOSEN_LINKER_NOTE,
                "scope_note": build_service.BUILD_SCOPE_NOTE,
            }
            # One worked example per route, so the assembly can be verified against something
            # the service itself produced rather than only against the interface's own output.
            if scaffolds and linkers:
                example = build_router.build(
                    direction=directions, route_id=route.id,
                    scaffold_id=scaffolds[0].id, linker_id=linkers[0].id,
                    limit=10, offset=0,
                )
                recipes["routes"][route.id]["example"] = {
                    "scaffold_id": scaffolds[0].id,
                    "linker_id": linkers[0].id,
                    "items": [
                        {
                            "id": item.id,
                            "full_sequence": item.full_sequence,
                            "fused_length": item.fused_length,
                            "segments": _dump(item.segments),
                        }
                        for item in example.items
                    ],
                }
        self.write("assembly.json", recipes)

    # -- raw predictor output -------------------------------------------------

    def peptide_details(self) -> None:
        """Every predictor's raw output per peptide, including the `details` JSONB.

        This is what makes an assembled score checkable against its source rather than taken on
        trust, and it is the one payload that would be expensive to reproduce later, because
        it lives in a table that is being copied off a machine nobody controls.
        """
        rows, total = constructs_repo.list_constructs(limit=100000, offset=0)
        out: dict[str, Any] = {}
        for row in rows:
            public_id = construct_service.public_id(row["id"])
            out[public_id] = {
                "construct_id": public_id,
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
                "stored_construct_scores": constructs_repo.scores_of(row),
                "stored_delivery_scores": constructs_repo.delivery_scores_of(row),
            }
        self.write("peptide_details.json", out)

    # -- driver ---------------------------------------------------------------

    def run(self, *, include_builds: bool = True, include_peptide_details: bool = True) -> None:
        started = time.time()
        self.meta()
        self.health()
        self.scaffolds()
        self.linkers()
        self.constructs()
        self.composites_by_route()
        if include_builds:
            self.builds()
            self.assembly_recipes()
        if include_peptide_details:
            self.peptide_details()
        # The manifest goes last: it indexes everything above, so it can only be written once
        # the file list is final.
        self.publish_manifest()
        elapsed = time.time() - started
        log.info(
            "%d files, %.1f MB, %.1fs%s",
            self.files, self.bytes / 1e6, elapsed, " (dry run, nothing written)"
            if self.dry_run else "",
        )


def _safe(identifier: str) -> str:
    """A filename fragment that round-trips an id containing a slash or a space."""
    return identifier.replace("/", "_").replace(" ", "_")


def _directions_key(names: list[str]) -> str:
    """The filename a direction set is written under: members sorted, joined with `+`.

    Sorted rather than in the order the set was requested, so one set has one name, and by the
    same rule the interface applies — the default sort on both sides, which orders these ASCII
    ids identically.
    """
    return "+".join(sorted(names))


def _prune_previous_export(out_dir: Path) -> int:
    """Delete a previous export from `out_dir` and report how many files went.

    A stale file is worse than a missing one. `manifest.json` lists what this export
    contains, but the static layer resolves a path straight to a file, so a construct, a
    scaffold or a Builder ranking left over from an earlier run would still be served — and
    the ones that matter are exactly the ones that no longer should exist.

    The presence of `manifest.json` is what identifies the directory as one of ours, so a
    mistyped `--out` cannot delete unrelated files.
    """
    if not (out_dir / "manifest.json").exists():
        return 0
    removed = sum(1 for p in out_dir.rglob("*") if p.is_file() or p.is_symlink())
    shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", required=True,
        help="Output directory. `../app/public/data` puts the files where Vite serves them.",
    )
    parser.add_argument(
        "--backend", choices=["auto", "postgres", "sqlite"], default=None,
        help="Which source to read. Defaults to the configured backend; `sqlite` exports the "
             "bundled fixture and is what a test run uses.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Count what would be written without touching the filesystem.",
    )
    parser.add_argument(
        "--skip-builds", action="store_true",
        help="Skip the Builder rankings, which are the most expensive part of the export.",
    )
    parser.add_argument(
        "--skip-peptide-details", action="store_true",
        help="Skip the raw per-predictor output.",
    )
    parser.add_argument(
        "--allow-fixture", action="store_true",
        help="Export from the bundled fixture anyway. Off by default because a deployment "
             "built from it would present four hand-made constructs as the library; the only "
             "reason to pass it is to exercise the static layer locally.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

    if args.backend:
        os.environ["IGEM_DB_BACKEND"] = args.backend
        get_settings.cache_clear()

    db.init_pool()
    try:
        db.ping()
    except Exception as exc:  # noqa: BLE001
        log.error("cannot reach the database: %s", exc)
        log.error(
            "Nothing was exported. A static build has to be produced from the real instance: "
            "a build exported from the bundled fixture would ship four hand-made constructs "
            "and present them as the library."
        )
        return 1

    backend = db.get_backend()
    if backend == "sqlite" and not args.allow_fixture:
        # A warning was not enough. This export is what a deployment ships, and nothing
        # downstream can tell a fixture-derived one from a real one except the
        # `source_backend` field it has to be told to look at — so the refusal is here, where
        # the mistake is cheap, rather than in a banner the reader has to notice.
        log.error(
            "refusing to export from the bundled SQLite fixture: it holds four hand-made "
            "constructs and no pipeline data, and a deployment built from it would present "
            "them as the library. Pass --allow-fixture to export it deliberately."
        )
        return 1
    if backend == "sqlite":
        log.warning(
            "exporting from the bundled SQLite fixture as requested: four hand-made "
            "constructs, no pipeline data"
        )

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        stale = _prune_previous_export(out_dir)
        if stale:
            log.info("replaced a previous export: %d stale files removed from %s", stale, out_dir)
    Exporter(out_dir, dry_run=args.dry_run).run(
        include_builds=not args.skip_builds,
        include_peptide_details=not args.skip_peptide_details,
    )
    log.info("written to %s", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
