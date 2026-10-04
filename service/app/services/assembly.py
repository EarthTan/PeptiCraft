"""Fused-sequence assembly.

A construct is `backbone + linker + peptide`. The linker and the peptide are both real: the
peptide comes from `peptides.sequence` via `constructs.peptide_id`, and the linker from
`linkers.sequence` via `constructs.linker_id`, which resolves to `GGGGS`. The backbone is
the problem.

Every one of the 496 rows points at `backbone_proteins.id = 1`, and that row holds the string
`PLACEHOLDER_4RepCT` with `length = 0`. The assembly script that wrote them says why, and it
is worth quoting because it states outright that the missing piece is this service's job:

    当前骨架 / linker 都是 PLACEHOLDER（src/setup/sql/12_create_constructs.sql）。
    真实 backbone / linker 序列与场景绑定由前端 + 后端构造器计算服务负责，本脚本只
    负责把"肽 × 占位骨架 × 占位 linker"的最小可行组合落库，让 constructs 表 schema
    与示例数据齐备即可。

So the stored binding is a stand-in, and `4RepCT` is itself a name from a retired mock
scaffold library — it is not one of the eight proteins in the real curated library.
Returning `4RepCT + GGGGS + peptide` as a fused sequence would therefore be a fabrication
that looks exactly like a real answer.

Three behaviours are offered instead, and the response always says which one produced it:

  * Stored and real — `BackboneBinding.verified`. The row `backbone_id` resolves to carries
    an amino-acid sequence rather than a marker string, so that sequence is used and a full
    fused sequence is emitted. The scores beside it still describe the peptide alone; the
    scaffold's effect on folding, exposure and aggregation is not modelled, so this is an
    assembled sequence plus a peptide-level prediction, not a measurement of the fusion
    protein.
  * Default — `BackboneBinding.placeholder`. No backbone is invented. `full_sequence` is
    null, the backbone segment is marked unavailable, and the linker and peptide segments
    are returned so the viewer still shows the real parts.
  * Explicit — when a caller names a scaffold (`?scaffold=<id>`), that scaffold's real
    sequence is used and the binding is reported as `BackboneBinding.inferred`, with a note
    that the choice came from the caller rather than from the pipeline. A request-time
    scaffold overrides a stored binding, because the response has to say which one it used.

Whether a sequence counts as real is decided in one place, `is_placeholder_backbone`, so the
assembler and the service that reports the binding cannot disagree about it.
"""
from __future__ import annotations

from typing import Any

from ..models.common import BackboneBinding
from ..models.construct import SequenceSegment

SEGMENT_COLORS = {
    "backbone": "#3b82f6",
    "linker": "#10b981",
    "peptide": "#f59e0b",
}

# The name the placeholder row in backbone_proteins carries. Recognised explicitly rather
# than inferred from a zero length, so that a genuinely short scaffold would not be
# mistaken for a placeholder.
PLACEHOLDER_MARKER = "PLACEHOLDER"


def is_placeholder_backbone(name: str | None, sequence: str | None) -> bool:
    if not name:
        return True
    if PLACEHOLDER_MARKER in (name or "").upper():
        return True
    if PLACEHOLDER_MARKER in (sequence or "").upper():
        return True
    return not sequence


def scaffold_sequence_for(
    scaffold: dict[str, Any] | None,
    sequences: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    """Pick the sequence to use for a scaffold.

    The cluster's representative sequence is the longest variant, which is the same choice
    the frontend generator makes, so a scaffold shows one consistent sequence in both
    places. A named variant overrides it.
    """
    if scaffold is None:
        return None, None
    if sequences:
        variant_id = sequences.get("sequence_id")
        if variant_id:
            return sequences.get("aa_sequence"), variant_id
    return scaffold.get("aa_sequence"), None


def assemble(
    *,
    peptide_sequence: str,
    linker_sequence: str | None,
    linker_name: str | None,
    scaffold: dict[str, Any] | None,
    scaffold_sequence: str | None,
    scaffold_variant: str | None,
    binding: BackboneBinding,
) -> tuple[str | None, list[SequenceSegment], bool, str]:
    """Return `(full_sequence, segments, assembled, note)`."""

    backbone_known = bool(scaffold_sequence) and not is_placeholder_backbone(
        scaffold.get("name") if scaffold else None, scaffold_sequence
    )
    linker_known = bool(linker_sequence)
    peptide_known = bool(peptide_sequence)

    segments: list[SequenceSegment] = []

    if backbone_known:
        assert scaffold is not None
        label = f"Backbone: {scaffold.get('short_name') or scaffold.get('name')}"
        if scaffold_variant:
            label = f"{label} ({scaffold_variant})"
        segments.append(SequenceSegment(
            label=label,
            sequence=scaffold_sequence or "",
            color=SEGMENT_COLORS["backbone"],
            type="backbone",
            available=True,
        ))
    else:
        segments.append(SequenceSegment(
            label="Backbone: sequence unavailable",
            sequence="",
            color=SEGMENT_COLORS["backbone"],
            type="backbone",
            available=False,
        ))

    segments.append(SequenceSegment(
        label=f"Linker: {linker_name}" if linker_known else "Linker: sequence unavailable",
        sequence=linker_sequence or "",
        color=SEGMENT_COLORS["linker"],
        type="linker",
        available=linker_known,
    ))

    segments.append(SequenceSegment(
        label="Peptide",
        sequence=peptide_sequence,
        color=SEGMENT_COLORS["peptide"],
        type="peptide",
        available=peptide_known,
    ))

    if backbone_known and linker_known and peptide_known:
        full = f"{scaffold_sequence}{linker_sequence}{peptide_sequence}"
        note = (
            "Assembled from the real scaffold sequence, the linker and the peptide."
            if binding == BackboneBinding.verified
            else (
                "Assembled with a scaffold chosen at request time. The stored construct does "
                "not carry a verified scaffold binding, so this sequence is a reconstruction "
                "rather than a pipeline output."
            )
        )
        return full, segments, True, note

    note = (
        "No fused sequence is emitted. The stored construct points at a placeholder "
        "scaffold row whose sequence is a marker string rather than an amino-acid sequence, "
        "so concatenating it would produce something that looks like a construct sequence "
        "but is not one. The linker and peptide segments below are real."
    )
    return None, segments, False, note
