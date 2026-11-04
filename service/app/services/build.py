"""The Builder's computation: assemble a candidate set against one scaffold and one linker.

The Builder asks a question the construct endpoints do not. `GET /api/constructs` reports what
has been stored; this module answers what the candidates *become* once a route, a set of
directions, a scaffold and a linker have been chosen. Everything it needs already exists — the
score assembly in `services.constructs`, the scaffold resolution and sequence assembly in
`services.assembly`, the route profiles and weights in `services.reference` — so this module
introduces no threshold and no new judgement about a candidate. What it introduces is the
composition, and three decisions that the composition forces:

**Which rows are candidates.** The top channel only. The bottom channel is the negative-control
arm: real rows with real scores, written so that a comparison has a baseline. Ranking a control
marker among candidates makes both harder to read, and the pipeline's own pool statistics
already draw exactly this line — `scoring._raw_component_values` reads `channel="top"` when it
computes the weights. A build that admitted bottom rows would be ranking against a distribution
it is not scored on.

**What order they come in.** Sorted by the composite under the requested route, over the whole
candidate set, with `offset` and `limit` applied afterwards. A row's composite depends on its
direction's pool, and the pool is read independently of the request and cached per direction,
so the value for a given row does not move when the request is narrowed. Ordering everything
and then slicing is therefore the correct order, not merely a convenient one — and it is what
makes `offset` mean anything, which sorting a single page inside the browser never did.

**What the sequences are evidence of.** An assembled sequence is a reproduction, not a
measurement. Neither the scaffold nor the linker a build uses is evidence about the molecule's
behaviour: both change the concatenation and neither changes a score, and the pairing in both
cases comes from the caller. So the two are labelled by where they came from — `inferred` for a
named scaffold, still carrying a note saying so, and a separate linker note — and a build that
names neither inherits whatever each stored row records, at which point the rows can disagree
with one another.

One resolution serves the whole request. Both targets are looked up once and passed to every
row's assembly, because a build assembles one row per candidate and resolving inside the
assembly would issue one lookup per row over a network to another machine.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Sequence

from ..models.build import (
    BuildCounts,
    BuildResult,
    BuildThresholds,
    BuiltConstruct,
    DirectionThresholdOutcome,
)
from ..repositories import constructs as constructs_repo, scaffolds as scaffolds_repo
from . import constructs as construct_service, reference, scoring
from . import thresholds as thresholds_service

log = logging.getLogger("pepticraft.build")

# The arm a build ranks over. See the module docstring: this mirrors the channel the pool
# statistics are computed from, so candidates are ordered on the distribution they belong to.
CANDIDATE_CHANNEL = "top"

# A ceiling on how many rows one direction contributes. The largest direction in the database
# holds 170 candidates, so this cannot be reached by the current data; it exists so that a
# future direction cannot turn one request into an unbounded scan. Exceeding it raises rather
# than truncating, because a silently shortened ranking would read as a complete one.
CANDIDATE_CEILING = 2000

STORED_BINDING_NOTE = (
    "No scaffold was named for this build, so each candidate is shown with the scaffold its "
    "own stored binding resolves to. The rows can therefore disagree with one another: a "
    "construct whose stored binding carries a real sequence assembles into a full fused "
    "sequence, and one whose binding is a placeholder emits none. `backbone_binding` on each "
    "row reports which case that row is."
)

# The linker notes are written here rather than reused from `services.constructs`, because
# the same fact has to be stated about a candidate set instead of about one construct. The
# two are otherwise the same account, and a caller that names a linker sees the same
# provenance in both places.
CHOSEN_LINKER_NOTE = (
    "The linker was named for this build rather than read from the stored rows, so every "
    "candidate is assembled with the same one and none with the linker its own row records. "
    "It is a real sequence out of the linker library, so each fused sequence is a "
    "concatenation of three real parts and what is a reconstruction is the pairing, not the "
    "parts. Naming a linker changes the assembled sequence and nothing else: the candidate "
    "set, the scores and the ranking are identical to those of a build that named none."
)

STORED_LINKER_NOTE = (
    "No linker was named, so each candidate keeps the linker its own stored row records, and "
    "the rows can differ from one another. A stored linker resolves against the sample "
    "`linkers` table rather than the curated library: its sequence is a real amino-acid "
    "sequence and `source_table` on it says which table answered, but it was attached by the "
    "assembly script rather than chosen."
)

BUILD_SCOPE_NOTE = (
    "Every score shown beside a candidate describes the functional peptide alone. The "
    "scaffold's effect on that peptide's folding, exposure or aggregation has not been "
    "modelled, and no predictor in the pipeline was run on the fusion protein. The assembled "
    "sequence and the scores are therefore two separate pieces of information about one "
    "candidate, not a measurement of the construct."
)


def _dedupe(values: Iterable[str]) -> list[str]:
    """Order-preserving dedupe.

    A repeated direction would otherwise be fetched twice and ranked twice, inflating both the
    ranking and the tally while looking like a legitimate request.
    """
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)


def _candidate_rows(direction: str) -> tuple[list[dict[str, Any]], int]:
    """Every candidate the direction holds, and the stored count it came from."""
    rows, total = constructs_repo.list_constructs(
        directions=[direction],
        channel=CANDIDATE_CHANNEL,
        limit=CANDIDATE_CEILING,
        offset=0,
    )
    if total > CANDIDATE_CEILING:
        raise RuntimeError(
            f"direction {direction!r} holds {total} candidates, above the {CANDIDATE_CEILING} "
            "this endpoint will rank in one request. Raise CANDIDATE_CEILING in "
            "services/build.py, or paginate the ranking in SQL, but do not return a partial "
            "ranking as though it were the whole one."
        )
    return rows, total


class _Candidate:
    """One computed candidate row, before it is assembled."""

    __slots__ = ("row", "assembled")

    def __init__(self, row: dict[str, Any], assembled) -> None:
        self.row = row
        self.assembled = assembled


def _rank_key(candidate: _Candidate) -> tuple:
    """Composite descending, candidates without one last, ties broken deterministically.

    `composite` is nullable and null means "no composite could be computed under this route",
    which is not the same as a low one. Sorting them to the end keeps an unrankable row from
    displacing a ranked one, and the stored rank and id follow so that two rows with equal
    composites keep a fixed order between requests.
    """
    composite = candidate.assembled.scores.composite
    stored_rank = candidate.row.get("rank")
    return (
        composite is None,
        -(composite if composite is not None else 0.0),
        stored_rank if stored_rank is not None else 10**9,
        candidate.row["id"],
    )


def _counts(candidates: Sequence[_Candidate]) -> BuildCounts:
    tally = {"clear": 0, "borderline": 0, "vetoed": 0, "indeterminate": 0}
    without_composite = 0
    for candidate in candidates:
        verdict = candidate.assembled.safety.verdict
        # An unrecognised verdict is counted as indeterminate rather than dropped, so the
        # tally always sums to `ranked` and a new verdict value cannot make rows disappear.
        tally[verdict if verdict in tally else "indeterminate"] += 1
        if candidate.assembled.scores.composite is None:
            without_composite += 1
    return BuildCounts(ranked=len(candidates), without_composite=without_composite, **tally)


def _apply_thresholds(
    candidates: Sequence[_Candidate],
    thresholds: thresholds_service.Thresholds,
    directions: Sequence[str],
) -> tuple[list[_Candidate], BuildThresholds]:
    """Filter the candidate set and cap what each direction contributes.

    The filter runs before the ranking, which is the same result either way — a threshold
    does not depend on a candidate's position — but it keeps the ranking over exactly the
    rows that survived, so the per-direction cap below counts the right rows.

    The cap runs after the ranking, because "the first N of a direction" is only meaningful
    once the direction's own order exists.
    """
    pool_by_direction: dict[str, int] = {}
    removed_by_direction: dict[str, int] = {}
    unassessed_by_direction: dict[str, int] = {}
    kept: list[_Candidate] = []

    for candidate in candidates:
        direction = candidate.row["direction"]
        pool_by_direction[direction] = pool_by_direction.get(direction, 0) + 1
        reason = thresholds_service.rejection_reason(candidate, thresholds)
        if reason is not None:
            removed_by_direction[direction] = removed_by_direction.get(direction, 0) + 1
            continue
        unassessed = thresholds_service.unassessed_count(candidate, thresholds)
        if unassessed:
            unassessed_by_direction[direction] = (
                unassessed_by_direction.get(direction, 0) + 1
            )
        kept.append(candidate)

    removed_by_cap: dict[str, int] = {}
    if thresholds.per_direction_limit is not None:
        seen: dict[str, int] = {}
        capped: list[_Candidate] = []
        for candidate in kept:
            direction = candidate.row["direction"]
            count = seen.get(direction, 0)
            if count >= thresholds.per_direction_limit:
                removed_by_cap[direction] = removed_by_cap.get(direction, 0) + 1
                continue
            seen[direction] = count + 1
            capped.append(candidate)
        kept = capped

    outcomes: list[DirectionThresholdOutcome] = []
    for direction in directions:
        floor = thresholds.functional_floor.get(direction)
        applied = floor is not None and thresholds_service.floor_applies(direction)
        note = None
        if floor is not None and not applied:
            note = (
                "This direction's score orders candidates rather than measuring activity, "
                "so a floor on it has no meaning and was not applied. Use the per-direction "
                "cap instead."
            )
        outcomes.append(
            DirectionThresholdOutcome(
                direction=direction,
                pool=pool_by_direction.get(direction, 0),
                kept=sum(1 for c in kept if c.row["direction"] == direction),
                removed_by_threshold=removed_by_direction.get(direction, 0),
                removed_by_cap=removed_by_cap.get(direction, 0),
                unassessed=unassessed_by_direction.get(direction, 0),
                functional_score_floor=floor,
                functional_score_floor_applied=applied,
                note=note,
            )
        )

    report = BuildThresholds(
        functional_score_floor=dict(thresholds.functional_floor),
        max_allergenicity=thresholds.max_allergenicity,
        min_peptide_length=thresholds.min_peptide_length,
        max_peptide_length=thresholds.max_peptide_length,
        per_direction_limit=thresholds.per_direction_limit,
        removed=sum(removed_by_direction.values()),
        removed_by_cap=sum(removed_by_cap.values()),
        directions=outcomes,
    )
    return kept, report


def _built(
    candidate: _Candidate, *, targets: construct_service.AssemblyTargets
) -> BuiltConstruct:
    """Assemble one ranked candidate against the build's scaffold and linker."""
    row = candidate.row
    a = candidate.assembled
    assembled_row = construct_service.assemble(row, targets=targets)

    return BuiltConstruct(
        id=construct_service.public_id(row["id"]),
        name=construct_service.public_id(row["id"]),
        direction=row["direction"],
        channel=row["channel"] or CANDIDATE_CHANNEL,
        status=row["status"] or "WIP",
        rank=row.get("rank"),
        direction_label=construct_service.direction_label(row["direction"]),
        peptide_sequence=row["peptide_sequence"],
        peptide_length=row["peptide_length"],
        backbone_name=assembled_row.backbone_name,
        backbone_id=assembled_row.scaffold_view.id if assembled_row.scaffold_view else None,
        # The linker actually used on this row, which is the named one when the build named
        # one and the row's own otherwise.
        linker_name=assembled_row.linker_name,
        functional_score=a.functional_value,
        functional_score_key=a.functional_key,
        functional_score_label=scoring.functional_label(a.functional_key),
        semantics=a.semantics,
        composite=a.scores.composite,
        safety_verdict=a.safety.verdict,
        allergenicity=a.supplementary.allergenicity,
        backbone_binding=assembled_row.binding,
        full_sequence=assembled_row.full_sequence,
        fused_length=len(assembled_row.full_sequence) if assembled_row.full_sequence else None,
        assembled_sequence_available=assembled_row.assembled,
        segments=assembled_row.segments,
    )


def build_candidates(
    *,
    directions: Iterable[str],
    route_id: str,
    scaffold_id: str | None = None,
    linker_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    thresholds: thresholds_service.Thresholds | None = None,
) -> BuildResult:
    """Assemble the candidates for one (route, scaffold, linker) combination.

    `route_id` must be a declared route and every direction must be a declared direction; the
    router validates both before calling, so this function treats them as known. The two
    assembly targets are resolved here, once, rather than inside the per-row assembly.

    `thresholds` narrows the candidate set before the ranking is sliced. The default set
    filters nothing, so a build that asks for none ranks exactly what it always ranked.
    """
    ordered_directions = _dedupe(directions)
    targets = construct_service.resolve_targets(scaffold_id=scaffold_id, linker_id=linker_id)
    thresholds = thresholds or thresholds_service.Thresholds()

    rows_by_direction: dict[str, list[dict[str, Any]]] = {}
    for direction in ordered_directions:
        rows, _total = _candidate_rows(direction)
        rows_by_direction[direction] = rows

    all_rows = [row for direction in ordered_directions for row in rows_by_direction[direction]]

    # One enrichment query for the whole set rather than one per direction: the predictor
    # rows are keyed by peptide, so batching across directions costs nothing.
    enriched_by_peptide = construct_service.load_enrichment(all_rows)

    candidates = [
        _Candidate(
            row,
            construct_service.compute(
                row, enriched_by_peptide.get(row["peptide_id"], {}), route_id
            ),
        )
        for row in all_rows
    ]
    candidates.sort(key=_rank_key)

    kept, threshold_report = _apply_thresholds(candidates, thresholds, ordered_directions)

    page = kept[offset: offset + limit]
    items = [_built(candidate, targets=targets) for candidate in page]

    kept_totals = {direction: 0 for direction in ordered_directions}
    for candidate in kept:
        direction = candidate.row["direction"]
        kept_totals[direction] = kept_totals.get(direction, 0) + 1

    route = reference.ROUTES_BY_ID[route_id]
    scaffold_view = (
        construct_service.scaffold_summary(targets.scaffold) if targets.scaffold else None
    )

    result = BuildResult(
        route=reference.route_with_scaffolds(
            route, [s["id"] for s in scaffolds_repo.list_scaffolds(route_id)]
        ),
        scaffold=scaffold_view,
        linker=targets.linker,
        binding_note=(
            construct_service.INFERRED_BINDING_NOTE if scaffold_view
            else STORED_BINDING_NOTE
        ),
        linker_note=(
            CHOSEN_LINKER_NOTE if targets.linker is not None else STORED_LINKER_NOTE
        ),
        scope_note=BUILD_SCOPE_NOTE,
        directions=ordered_directions,
        totals=kept_totals,
        total=sum(kept_totals.values()),
        counts=_counts(kept),
        thresholds=threshold_report,
        items=items,
        limit=limit,
        offset=offset,
    )
    log.info(
        "build: route=%s directions=%s scaffold=%s linker=%s ranked=%d returned=%d "
        "thresholds_removed=%d",
        route_id, ordered_directions, scaffold_id, linker_id, len(kept), len(items),
        threshold_report.removed,
    )
    return result
