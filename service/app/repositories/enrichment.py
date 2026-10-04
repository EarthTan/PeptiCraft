"""Read access to `peptide_enrichment` — the per-tool score table.

This is where eight of the nine rendered scores actually live. `constructs.scores` only
carries six direction-independent keys plus a per-direction functional key; thermal
stability and solubility are absent from it entirely, which made it look as though those two
predictors had never been run. They have: `temstapro` and `sodope` each hold 20,248,885 rows
in this table, and every one of the 496 construct peptides has a value for both.

Access is always by `peptide_id` so the `(peptide_id, tool)` primary key is usable. The
seqscan settings are requested here and nowhere else: this table is 377 M rows in 130 GB
and the planner will otherwise pick a sequential scan, while `constructs` is 496 rows and
is genuinely cheaper to scan in full.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

from .. import db

# The tool names as stored. Note the two spellings that matter: the enrichment table uses
# `bepipred3` (current) while `constructs.scores` uses `bepipred` for the 170 antioxidant
# rows, and `netmhcipan` appears in neither — its output only reaches constructs.scores as
# an already-aggregated percent rank.
TOXINPRED3 = "toxinpred3"
HEMOPI2 = "hemopi2"
SODOPE = "sodope"
TEMSTAPRO = "temstapro"
BEPIPRED3 = "bepipred3"
PLM4CPPS = "plm4cpps"
ALGPRED2 = "algpred2"
MHCFLURRY = "mhcflurry"
ANOXPEPRED = "anoxpepred"
ANOXPEPRED_FRS = "anoxpepred-frs"
ANOXPEPRED_CHEL = "anoxpepred-chelating"
AOPXSVM = "aopxsvm"
AMP_ESM = "amp-esm"
IMFP_LG_AMP = "imfp_lg_AMP"
IMFP_LG_AIP = "imfp_lg_AIP"
IMFP_LG_ACP = "imfp_lg_ACP"
IMFP_LG_ADP = "imfp_lg_ADP"
IMFP_LG_AHP = "imfp_lg_AHP"
TIPRED = "tipred"

# The functional score each direction is ranked by, and the semantics of that number.
# Both antimicrobial and anti-inflammatory candidates have two plausible functional tools;
# the choice is declared here rather than left implicit, and travels to the client in
# `ConstructDetail.semantics` so the UI never renders a ranking score as a probability.
FUNCTIONAL_SCORE_BY_DIRECTION: dict[str, tuple[str, str]] = {
    "antioxidant": (ANOXPEPRED_FRS, "probability"),
    "antibacterial": (IMFP_LG_AMP, "probability"),
    "anti_inflammatory": (IMFP_LG_AIP, "ranking_only"),
    "antimelanin": (TIPRED, "probability"),
}


def scores_for_peptides(
    peptide_ids: Sequence[int],
    tools: Sequence[str] | None = None,
) -> dict[int, dict[str, dict[str, Any]]]:
    """Return `{peptide_id: {tool: {score, label, details}}}`.

    One round trip per batch. Callers batch because a Results page needs seven tools for one
    peptide while a Library listing needs seven tools for fifty, and the difference between
    seven round trips and one is the difference between a usable list and a slow one.
    """
    if not peptide_ids:
        return {}

    sql = "SELECT peptide_id, tool, score, label, details FROM peptide_enrichment WHERE peptide_id = ANY(%s)"
    params: list[Any] = [list(peptide_ids)]
    if tools:
        sql += " AND tool = ANY(%s)"
        params.append(list(tools))

    out: dict[int, dict[str, dict[str, Any]]] = {}
    for row in db.query(sql, params, force_index=True):
        details = row.get("details")
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except json.JSONDecodeError:
                details = {}
        out.setdefault(row["peptide_id"], {})[row["tool"]] = {
            "score": row.get("score"),
            "label": row.get("label"),
            "details": details or {},
        }
    return out


def tool_coverage(peptide_ids: Sequence[int]) -> dict[str, int]:
    """How many of the given peptides have a row per tool.

    Served through `/api/meta/tools` so the interface can state coverage per predictor
    instead of implying that every score is available for every candidate. MHCflurry's
    coverage in particular is 117 of 496, and presenting the other 379 as "failed" rather
    than "not assessed" would be a factual error.
    """
    if not peptide_ids:
        return {}
    rows = db.query(
        """
        SELECT tool, count(*) AS n
          FROM peptide_enrichment
         WHERE peptide_id = ANY(%s)
         GROUP BY tool
        """,
        [list(peptide_ids)],
        force_index=True,
    )
    return {r["tool"]: int(r["n"]) for r in rows}


def distinct_tools() -> list[str]:
    return [r["tool"] for r in db.query("SELECT DISTINCT tool FROM peptide_enrichment ORDER BY tool",
                                       force_index=True)]


def details_for_peptide(peptide_id: int) -> list[dict[str, Any]]:
    """Every tool's output for one peptide, for the peptide detail view."""
    rows = db.query(
        """
        SELECT tool, score, label, details, scored_at
          FROM peptide_enrichment
         WHERE peptide_id = %s
         ORDER BY tool
        """,
        [peptide_id],
        force_index=True,
    )
    for row in rows:
        details = row.get("details")
        if isinstance(details, str):
            try:
                row["details"] = json.loads(details)
            except json.JSONDecodeError:
                row["details"] = {}
    return rows
