"""Turns database rows into the construct models the API serves.

One place assembles a construct, so the list and detail responses cannot disagree about a
score. The list is a trimmed view of the same computation rather than a separate query path
with its own rules.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Sequence

from ..models.common import BackboneBinding
from ..models.construct import (
    ConstructDetail,
    ConstructSummary,
    DeliveryAdjustedScores,
    PeptideInfo,
    SafetyVerdict,
)
from ..models.linker import LinkerView
from ..models.scaffold import ScaffoldSummary
from ..repositories import constructs as constructs_repo
from ..repositories import enrichment, scaffolds as scaffolds_repo
from . import assembly, linkers as linker_service, reference, scoring

log = logging.getLogger("pepticraft.constructs")

# The scenario strings the pipeline wrote, and which application routes each one plausibly
# belongs to. This is a hint for narrowing a candidate list, NOT a binding: the stored
# constructs carry no verified scaffold, and `scenario` records the pipeline run rather than
# a product decision.
SCENARIO_ROUTE_HINT: dict[str, list[str]] = {
    "wound_care": ["wound-dressing"],
    "wound_careing": ["wound-dressing"],
    "inflammation": ["wound-dressing", "topical-film"],
    "depigmentation": ["mask-patch", "topical-film", "hair-coating"],
}

PLACEHOLDER_BINDING_NOTE = (
    "The stored construct points at `backbone_proteins.id = 1`, a placeholder row whose "
    "sequence is the marker string `PLACEHOLDER_4RepCT` with length 0. The assembly script "
    "that wrote these rows states that the real backbone sequence and its scenario binding "
    "are the responsibility of a backend construct-calculation service, and persisted a "
    "minimal combination so that the schema and sample data would be complete. The name "
    "`4RepCT` also comes from a retired mock scaffold library and is not one of the eight "
    "proteins in the curated library. No fused sequence is emitted for this construct."
)

VERIFIED_BINDING_NOTE = (
    "The stored construct carries a scaffold binding whose row holds a real amino-acid "
    "sequence, so the fused sequence is assembled from data already recorded against the "
    "construct rather than from a scaffold named at request time. The scores beside it still "
    "describe the functional peptide alone: the scaffold's effect on that peptide's folding, "
    "exposure or aggregation has not been modelled, so this is an assembled sequence plus a "
    "peptide-level activity prediction, not a measurement of the fusion protein."
)

INFERRED_BINDING_NOTE = (
    "The scaffold was named at request time rather than read from the stored construct. The "
    "fused sequence uses that scaffold's real sequence, so it is a faithful assembly of a "
    "real scaffold with a real linker and peptide, but the scaffold-to-construct assignment "
    "is a reconstruction and not a pipeline output."
)

CHOSEN_LINKER_NOTE = (
    "The linker was named at request time rather than read from this construct's record, so "
    "the fused sequence is built with an entry the construct does not itself hold. It is a "
    "real sequence out of the linker library, so the reconstruction is in the pairing and not "
    "in the parts. Naming a linker changes the assembled sequence and nothing else."
)

STORED_LINKER_NOTE = (
    "No linker was named, so this construct keeps the linker its own stored row records. "
    "That linker resolves against the sample `linkers` table rather than the curated library: "
    "its sequence is a real amino-acid sequence and `source_table` on it says which table "
    "answered, but it was attached by the assembly script rather than chosen."
)


def stored_backbone(row: dict[str, Any]) -> tuple[dict[str, Any] | None, BackboneBinding]:
    """The scaffold a stored construct points at, and whether it is real.

    A construct's `backbone_id` resolves against `backbone_proteins`, a different table from
    the curated `scaffold_library`. The row it lands on is a marker-string placeholder for
    every construct the pipeline wrote, and it would be a real scaffold for a construct whose
    binding was set properly. The service previously had no way to tell the two apart in its
    output — it reported `placeholder` unconditionally — so a construct with a genuinely
    recorded scaffold could never produce a fused sequence even when the data supported it.

    The placeholder test is the assembler's own, so the two cannot disagree about whether a
    sequence is usable.
    """
    name = row.get("backbone_name")
    sequence = row.get("backbone_sequence")
    if assembly.is_placeholder_backbone(name, sequence):
        return None, BackboneBinding.placeholder
    return (
        {
            "name": name,
            "short_name": name,
            "aa_sequence": sequence,
            "length_aa": row.get("backbone_length"),
        },
        BackboneBinding.verified,
    )


def public_id(db_id: int) -> str:
    return f"con_{db_id:04d}"


def direction_label(direction: str) -> str:
    meta = reference.DIRECTIONS_BY_ID.get(direction)
    return meta["name"] if meta else direction


# ---------------------------------------------------------------------------
# Shared computation
# ---------------------------------------------------------------------------

class Assembled:
    """Everything derived from one construct row, computed once."""

    __slots__ = ("row", "scores", "supplementary", "score_meta", "semantics",
                 "delivery", "safety", "enriched", "functional_value", "functional_key")

    def __init__(self, row, scores, supplementary, score_meta, semantics,
                 delivery, safety, enriched, functional_value, functional_key):
        self.row = row
        self.scores = scores
        self.supplementary = supplementary
        self.score_meta = score_meta
        self.semantics = semantics
        self.delivery = delivery
        self.safety = safety
        self.enriched = enriched
        self.functional_value = functional_value
        self.functional_key = functional_key


def load_enrichment(rows: Sequence[dict[str, Any]]) -> dict[int, dict[str, dict[str, Any]]]:
    peptide_ids = sorted({r["peptide_id"] for r in rows})
    return enrichment.scores_for_peptides(peptide_ids)


def compute(row: dict[str, Any],
            enriched: dict[str, dict[str, Any]],
            route_id: str | None) -> Assembled:
    direction = row["direction"]
    stored = constructs_repo.scores_of(row)
    scores, supplementary, meta, semantics = scoring.assemble_scores(direction, stored, enriched)

    # One route drives both derived results. The composite always needed a route, and the
    # safety verdict needs one too: the immunogenicity gate is the route's threshold, so
    # evaluating safety with no route dropped that gate entirely rather than defaulting it —
    # a response with no route named came back "clear" with the immunogenicity veto gate
    # simply absent from the gate list, which reads as a pass. The router documents the
    # default as the first declared route, and this is where that default is applied.
    effective_route = route_id or reference.ROUTES[0].id

    delivery = scoring.composites_for_all_routes(direction, scores, supplementary)
    safety = scoring.evaluate_safety(scores, supplementary, effective_route)

    # The composite is route-dependent, so the flat `scores.composite` follows whichever
    # route the request named, and carries the selected route's value.
    selected = delivery.get(effective_route)
    if selected is not None:
        scores.composite = selected.composite
        meta["composite"] = scoring.ScoreMeta(
            key="composite",
            tool="Composite scorer",
            measures=reference.TOOLS_BY_KEY["composite"].measures,
            higher_is_better=True,
            group="developability",
            assessed=selected.composite is not None,
            semantics=scoring.ScoreSemantics.ranking_only,
            applied_threshold=None,
            is_veto_gate=False,
        )

    func_value, func_key, _ = scoring.functional_score(direction, enriched, stored)

    return Assembled(row, scores, supplementary, meta, semantics, delivery, safety,
                     enriched, func_value, func_key)


# ---------------------------------------------------------------------------
# Scaffold resolution
# ---------------------------------------------------------------------------

def scaffold_summary(scaffold: dict[str, Any]) -> ScaffoldSummary:
    return ScaffoldSummary(
        id=scaffold["id"],
        name=scaffold["name"],
        short_name=scaffold["short_name"],
        category=scaffold.get("category"),
        applicant=scaffold["applicant"],
        patent=scaffold.get("patent_family"),
        length=scaffold.get("length_aa"),
        species=scaffold.get("species"),
        sequence_count=scaffold.get("sequence_count") or 0,
        application_tags=list(scaffold.get("application_tags") or []),
        route_ids=list(scaffold.get("route_ids") or []),
        material_forms=list(scaffold.get("material_forms") or []),
        max_evidence=scaffold.get("max_evidence"),
        has_sequence=bool(scaffold.get("aa_sequence")),
    )


def scaffold_candidates(row: dict[str, Any]) -> list[ScaffoldSummary]:
    """Scaffolds plausibly usable with this construct, most evidenced first.

    Narrowed by the routes the construct's stored scenario hints at. Offered as a choice,
    never applied silently.
    """
    routes = SCENARIO_ROUTE_HINT.get(row.get("scenario") or "", [])
    seen: dict[str, dict[str, Any]] = {}
    for route_id in routes:
        for s in scaffolds_repo.list_scaffolds(route_id):
            seen[s["id"]] = s
    if not seen:
        for s in scaffolds_repo.list_scaffolds():
            seen[s["id"]] = s
    return [scaffold_summary(s) for s in seen.values()]


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssemblyTargets:
    """The scaffold and linker an assembly was told to use, already resolved.

    Resolution sits outside `assemble` so that a build resolves once for the whole request
    rather than once per row. Each field holds a real row or None; an id that names nothing
    becomes None here rather than raising, because deciding whether an unknown id is an
    error belongs to the router, which is the layer that reports it.
    """

    scaffold: dict[str, Any] | None = None
    linker: LinkerView | None = None


def resolve_targets(
    *, scaffold_id: str | None = None, linker_id: str | None = None
) -> AssemblyTargets:
    """Turn the ids a request named into rows."""
    return AssemblyTargets(
        scaffold=scaffolds_repo.get_scaffold(scaffold_id) if scaffold_id else None,
        linker=linker_service.view_for(linker_id),
    )


class RowAssembly:
    """A construct's fused sequence, and the account of where each part came from."""

    __slots__ = ("full_sequence", "segments", "assembled", "note",
                 "binding", "binding_note", "scaffold_view", "backbone_name",
                 "linker_view", "linker_name", "linker_note")

    def __init__(self, full_sequence, segments, assembled, note,
                 binding, binding_note, scaffold_view, backbone_name,
                 linker_view, linker_name, linker_note):
        self.full_sequence = full_sequence
        self.segments = segments
        self.assembled = assembled
        self.note = note
        self.binding = binding
        self.binding_note = binding_note
        self.scaffold_view = scaffold_view
        self.backbone_name = backbone_name
        self.linker_view = linker_view
        self.linker_name = linker_name
        self.linker_note = linker_note


def assemble(row: dict[str, Any], *, targets: AssemblyTargets) -> RowAssembly:
    """Assemble one construct against already-resolved targets.

    This is the only place the decisions about which scaffold and which linker an assembled
    sequence was built from are made, so a caller cannot reach a different answer about
    either. The scaffold has three cases, in priority order:

      * a scaffold named by the caller wins over whatever the row stores, and the result is
        reported as `inferred` — a reconstruction that the response has to label as one,
        because the row itself does not record that pairing;
      * otherwise, a stored binding whose row carries a real amino-acid sequence is
        `verified`, and the fused sequence is assembled from data already on the construct;
      * otherwise the binding is a placeholder and no fused sequence is emitted.

    The linker has two, and they are simpler because a stored linker is never a marker
    string: one named by the caller wins over the row's own, and otherwise the row's own is
    used. Which of the two happened is reported by `linker_note`, because a caller that
    named one has to be able to tell the sequence it got from the sequence on the record.
    """
    stored_scaffold, stored_binding = stored_backbone(row)

    if targets.scaffold is not None:
        binding = BackboneBinding.inferred
        binding_note = INFERRED_BINDING_NOTE
        assembly_scaffold = targets.scaffold
        scaffold_seq, variant = assembly.scaffold_sequence_for(targets.scaffold, None)
    elif stored_binding is BackboneBinding.verified:
        binding = BackboneBinding.verified
        binding_note = VERIFIED_BINDING_NOTE
        assembly_scaffold = stored_scaffold
        scaffold_seq = row.get("backbone_sequence")
        variant = None
    else:
        binding = BackboneBinding.placeholder
        binding_note = PLACEHOLDER_BINDING_NOTE
        assembly_scaffold = None
        scaffold_seq, variant = None, None

    # The curated `scaffold_library` view is filled in only for a request-time scaffold; a
    # stored binding resolves against `backbone_proteins`, which carries no curated metadata.
    scaffold_view = scaffold_summary(targets.scaffold) if targets.scaffold else None
    backbone_name = (
        scaffold_view.short_name if scaffold_view
        else (stored_scaffold["short_name"] if stored_binding is BackboneBinding.verified else None)
    )

    linker = targets.linker or stored_linker_view(row)

    full_sequence, segments, assembled, assembly_note = assembly.assemble(
        peptide_sequence=row["peptide_sequence"],
        linker_sequence=linker.sequence if linker else None,
        linker_name=linker.name if linker else None,
        scaffold=assembly_scaffold,
        scaffold_sequence=scaffold_seq,
        scaffold_variant=variant,
        binding=binding,
    )
    log.debug(
        "construct %s: binding=%s linker=%s assembled=%s (%s)",
        row["id"], binding, linker.name if linker else None, assembled, assembly_note,
    )
    return RowAssembly(
        full_sequence=full_sequence,
        segments=segments,
        assembled=assembled,
        note=assembly_note,
        binding=binding,
        binding_note=binding_note,
        scaffold_view=scaffold_view,
        backbone_name=backbone_name,
        linker_view=linker,
        linker_name=linker.name if linker else None,
        linker_note=linker_note_for(targets.linker),
    )


def assemble_row(
    row: dict[str, Any],
    *,
    scaffold_id: str | None = None,
    linker_id: str | None = None,
) -> RowAssembly:
    """Single-construct convenience: resolve the named ids, then assemble."""
    return assemble(row, targets=resolve_targets(scaffold_id=scaffold_id, linker_id=linker_id))


def stored_linker_view(row: dict[str, Any]) -> LinkerView | None:
    """The linker a stored construct records, built from the columns the row already joined.

    Read off the join rather than by a second lookup, because this runs once per candidate
    in a build: resolving each row's linker independently would turn one request into one
    query per row. `stored_backbone` above reads the joined columns the same way.

    The id is resolved against `linkers` and never against the curated library. A curated
    entry whose id happened to be numeric would otherwise shadow the row the construct
    actually points at, since `constructs.linker_id` is a foreign key to the sample table.
    """
    linker_id = row.get("linker_id")
    if linker_id is None:
        return None
    name = row.get("linker_name")
    sequence = row.get("linker_sequence")
    if name is None and sequence is None:
        return None
    return LinkerView(
        id=str(linker_id),
        # An identifier stands in when the row carries no name, rather than a phrase that
        # would read as the linker's own name.
        name=name or f"#{linker_id}",
        sequence=sequence or "",
        length=row.get("linker_length") or len(sequence or ""),
        rigidity=linker_service.band(row.get("linker_rigidity")),
        source_table="linkers",
        unit_composition=[],
        description=row.get("linker_description"),
        reference=None,
    )


def linker_note_for(chosen: LinkerView | None) -> str:
    """Where the linker a single construct's assembly used came from.

    A build writes its own notes rather than reusing these, because the same fact has to be
    stated about a candidate set instead of one construct — see `services/build.py`.
    """
    return CHOSEN_LINKER_NOTE if chosen is not None else STORED_LINKER_NOTE


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

def build_summaries(
    rows: Sequence[dict[str, Any]],
    enriched_by_peptide: dict[int, dict[str, dict[str, Any]]] | None = None,
    route_id: str | None = None,
) -> list[ConstructSummary]:
    enriched_by_peptide = enriched_by_peptide or load_enrichment(rows)
    out: list[ConstructSummary] = []
    for row in rows:
        enriched = enriched_by_peptide.get(row["peptide_id"], {})
        a = compute(row, enriched, route_id)
        stored_scaffold, binding = stored_backbone(row)
        out.append(ConstructSummary(
            id=public_id(row["id"]),
            name=public_id(row["id"]),
            direction=row["direction"],
            channel=row["channel"] or "top",
            status=row["status"] or "WIP",
            rank=row.get("rank"),
            direction_label=direction_label(row["direction"]),
            peptide_sequence=row["peptide_sequence"],
            peptide_length=row["peptide_length"],
            # Only a verified binding names a scaffold on the card. A placeholder binding
            # carries a marker string, not a scaffold name, and printing it would read as a
            # real choice.
            backbone_name=stored_scaffold["short_name"] if stored_scaffold else None,
            backbone_id=None,
            linker_name=row.get("linker_name"),
            functional_score=a.functional_value,
            functional_score_key=a.functional_key,
            functional_score_label=scoring.functional_label(a.functional_key),
            semantics=a.semantics,
            composite=a.scores.composite,
            safety_verdict=a.safety.verdict,
            backbone_binding=binding,
        ))
    return out


def build_detail(
    row: dict[str, Any],
    enriched: dict[str, dict[str, Any]],
    *,
    route_id: str | None = None,
    scaffold_id: str | None = None,
    linker_id: str | None = None,
) -> ConstructDetail:
    a = compute(row, enriched, route_id)
    assembled_row = assemble_row(row, scaffold_id=scaffold_id, linker_id=linker_id)

    unassessed = [k for k, m in a.score_meta.items() if not m.assessed]

    return ConstructDetail(
        id=public_id(row["id"]),
        name=public_id(row["id"]),
        direction=row["direction"],
        channel=row["channel"] or "top",
        status=row["status"] or "WIP",
        rank=row.get("rank"),
        direction_label=direction_label(row["direction"]),
        peptide_sequence=row["peptide_sequence"],
        peptide_length=row["peptide_length"],
        backbone_name=assembled_row.backbone_name,
        backbone_id=assembled_row.scaffold_view.id if assembled_row.scaffold_view else None,
        linker_name=row.get("linker_name"),
        functional_score=a.functional_value,
        functional_score_key=a.functional_key,
        functional_score_label=scoring.functional_label(a.functional_key),
        semantics=a.semantics,
        composite=a.scores.composite,
        safety_verdict=a.safety.verdict,
        backbone_binding=assembled_row.binding,
        backbone_binding_note=assembled_row.binding_note,
        scaffold=assembled_row.scaffold_view,
        linker=assembled_row.linker_view,
        linker_note=assembled_row.linker_note,
        peptide=PeptideInfo(
            id=row["peptide_id"],
            sequence=row["peptide_sequence"],
            length=row["peptide_length"],
            source=row["peptide_source"],
            source_version=str(row["peptide_source_version"]),
            source_accession=row.get("peptide_source_accession"),
            seq_md5=(row.get("peptide_md5") or "").strip(),
        ),
        full_sequence=assembled_row.full_sequence,
        assembled_sequence_available=assembled_row.assembled,
        segments=assembled_row.segments,
        scores=a.scores,
        supplementary=a.supplementary,
        score_meta=a.score_meta,
        delivery_scores=a.delivery,
        safety=a.safety,
        unassessed_metrics=unassessed,
        assessed_flags={k: m.assessed for k, m in a.score_meta.items()},
    )


# Re-exported so callers do not import from scoring directly for the common case.
DeliveryAdjustedScores = DeliveryAdjustedScores
SafetyVerdict = SafetyVerdict
