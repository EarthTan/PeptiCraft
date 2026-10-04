"""Reference-data queries: direction counts, scaffold route map, enrichment coverage."""
from __future__ import annotations

import threading
import time
from typing import Any

from .. import db
from . import constructs as constructs_repo
from . import scaffolds as scaffolds_repo

# The coverage view runs a full count over peptide_enrichment, 377 M rows in 130 GB, and
# takes about six seconds. The result changes only when a pipeline run finishes, so it is
# cached for the lifetime of the process and refreshed on an interval.
_COVERAGE_TTL_SECONDS = 600
_coverage_cache: tuple[float, list[dict[str, Any]]] | None = None
_coverage_lock = threading.Lock()

# The functional predictor each direction's score is taken from. These are the keys the
# pipeline actually ranked on, read out of each direction's `select.py`:
#   antioxidant      aopxsvm P90 cutoff, with AnOxPePred's FRS head as the reported
#                    activity probability — aopxsvm's stored value is a class label (0/1)
#                    with the probability tucked into `details.prob`, so it makes a poor
#                    displayed score
#   antibacterial    amp-esm, which is AMPlify v0.1.0 scored over the whole library
#   anti_inflammatory imfp_lg_AIP
#   antimelanin      tipred
#
# `v_peptide_enrichment_coverage` does not track the iMFP-LG channels, so a direction whose
# tool is absent from it falls back to a direct count.
DIRECTION_FUNCTIONAL_TOOL = {
    "antioxidant": "anoxpepred-frs",
    "antibacterial": "amp-esm",
    "anti_inflammatory": "imfp_lg_AIP",
    "antimelanin": "tipred",
}


def enrichment_coverage(refresh: bool = False) -> list[dict[str, Any]]:
    global _coverage_cache
    with _coverage_lock:
        if not refresh and _coverage_cache is not None:
            ts, rows = _coverage_cache
            if time.time() - ts < _COVERAGE_TTL_SECONDS:
                return rows
    rows = db.query("SELECT tool, done_count, eligible_count, coverage_pct "
                    "FROM v_peptide_enrichment_coverage ORDER BY tool")
    with _coverage_lock:
        _coverage_cache = (time.time(), rows)
    return rows


def coverage_by_tool(refresh: bool = False) -> dict[str, dict[str, Any]]:
    return {r["tool"]: r for r in enrichment_coverage(refresh=refresh)}


def direction_counts() -> dict[str, dict[str, Any]]:
    """Per-direction totals, channel split and status split, from `constructs`."""
    out: dict[str, dict[str, Any]] = {}
    for row in constructs_repo.direction_counts():
        d = out.setdefault(row["direction"], {
            "total": 0, "top": 0, "bottom": 0, "by_status": {},
        })
        n = int(row["n"])
        d["total"] += n
        if row["channel"] == "top":
            d["top"] += n
        elif row["channel"] == "bottom":
            d["bottom"] += n
        status = row["status"] or "unknown"
        d["by_status"][status] = d["by_status"].get(status, 0) + n
    return out


def precursor_counts() -> dict[str, int]:
    """How many peptides each direction's functional predictor scored.

    Read from the coverage view where the tool is tracked, and counted directly where it is
    not — the view lists twelve tools and omits the iMFP-LG channels. A direction cannot
    advertise a library size its predictor never covered, so a tool with no rows reports
    zero rather than the library total.
    """
    coverage = coverage_by_tool()
    cache: dict[str, int] = {}
    out: dict[str, int] = {}
    for direction, tool in DIRECTION_FUNCTIONAL_TOOL.items():
        entry = coverage.get(tool)
        if entry:
            out[direction] = int(entry["done_count"])
            continue
        if tool not in cache:
            cache[tool] = db.count(
                "SELECT count(*) AS n FROM peptide_enrichment WHERE tool = %s",
                [tool],
                force_index=True,
            )
        out[direction] = cache[tool]
    return out


def scaffold_route_map() -> dict[str, list[str]]:
    return scaffolds_repo.route_map()
