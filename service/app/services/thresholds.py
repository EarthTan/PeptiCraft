"""Screening thresholds a caller can set on a build.

A build ranks the candidates that already exist. A threshold decides which of them survive
the ranking. There are four, and each has a different reach — which is why they are set
separately rather than gathered into one "strictness" dial:

  * **A floor on the direction's functional score.** Per direction, because the four
    directions are ranked by four different predictors on four different scales: a floor of
    0.5 means something for AnOxPePred's free-radical head and something else entirely for
    AMPlify. It applies only where the score is a probability. The anti-inflammatory and
    anti-melanin scores are ranking signals — they order candidates and are not probabilities
    — so a floor on them would be a number with no meaning behind it. Those two directions
    are capped by count instead.

  * **A ceiling on the allergenicity score.** AlgPred2's own boundary, and the only threshold
    here that applies identically to every direction.

  * **A range on the peptide's length.** The platform works with peptides of 1-30 residues,
    and the candidate set spans that range unevenly, so the range is a real filter rather
    than a formality.

  * **A cap on how many candidates each direction contributes.** The substitute for a floor
    on a ranking-only direction, and the only way to hold several directions at once without
    one of them filling the page.

What the thresholds cannot do is widen the candidate set. Everything here filters the
candidates the pipeline produced; nothing here brings a new peptide in. The distinction
matters because the peptide library holds twenty million sequences and the candidate set
holds a few hundred.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..models.common import ScoreSemantics
from . import scoring

log = logging.getLogger("pepticraft.thresholds")


# The peptide length range the platform itself works within. These are the bounds the
# library was built to, not the bounds of the current candidate set, so the default range
# filters nothing and a narrower one the caller asks for is a deliberate narrowing.
PEPTIDE_LENGTH_MIN = 1
PEPTIDE_LENGTH_MAX = 30

# AlgPred2's own activity boundary. The predictor declares it, so it is the value the
# interface offers as the starting point.
ALLERGENICITY_BOUNDARY = 0.3


@dataclass(frozen=True)
class Thresholds:
    """The screening thresholds one build ran under.

    Every field is optional and the default set filters nothing, so a build that sets no
    threshold ranks exactly the candidate set it always did.
    """

    functional_floor: Mapping[str, float] = field(default_factory=dict)
    max_allergenicity: float | None = None
    min_peptide_length: int | None = None
    max_peptide_length: int | None = None
    per_direction_limit: int | None = None

    @property
    def active(self) -> bool:
        """Whether any threshold was set at all."""
        return bool(
            self.functional_floor
            or self.max_allergenicity is not None
            or self.min_peptide_length is not None
            or self.max_peptide_length is not None
            or self.per_direction_limit is not None
        )


def parse_functional_floor(raw: Sequence[str] | None) -> dict[str, float]:
    """Read the per-direction score floors.

    Both spellings are accepted — a repeated parameter and one value carrying several
    comma-separated entries — the same way the direction list itself is read. Each entry is
    `direction:value`.

    The separator is a colon rather than an equals sign because the equals sign already
    separates the parameter from its value, and `?min_functional_score=antioxidant=0.5`
    reads as a mistake even where it is not one.

    An entry that cannot be read is rejected rather than skipped. A floor the caller believes
    was applied and was not is worse than a failed request, because the ranking it produces
    looks complete either way.
    """
    values: dict[str, float] = {}
    for entry in raw or []:
        for part in entry.split(","):
            text = part.strip()
            if not text:
                continue
            direction, separator, number = text.partition(":")
            direction = direction.strip()
            if not separator:
                raise ValueError(
                    f"cannot read {text!r}: expected `direction:value`, for example "
                    "`antioxidant:0.5`"
                )
            try:
                floor = float(number.strip())
            except ValueError:
                raise ValueError(
                    f"cannot read {text!r}: {number.strip()!r} is not a number"
                ) from None
            values[direction] = floor
    return values


def floor_applies(direction: str) -> bool:
    """Whether a score floor means anything for this direction.

    A floor applies where the score is a probability. Where the score only orders
    candidates, a threshold on it would be a number the platform cannot interpret.
    """
    _, semantics = scoring.FUNCTIONAL_SCORE.get(direction, (None, ScoreSemantics.probability))
    return semantics == ScoreSemantics.probability


def rejection_reason(candidate: Any, thresholds: Thresholds) -> str | None:
    """Why this candidate does not pass the thresholds, or None when it does.

    A candidate whose value for a threshold is missing is not rejected. `null` in this
    platform means "not assessed", and a threshold cannot exclude what was never measured —
    the row stays in the ranking and the count of unassessed rows is reported separately.
    """
    row = candidate.row
    assembled = candidate.assembled
    direction = row["direction"]

    floor = thresholds.functional_floor.get(direction)
    if floor is not None and floor_applies(direction):
        value = assembled.functional_value
        if value is not None and value < floor:
            return "functional_score"

    if thresholds.max_allergenicity is not None:
        value = assembled.supplementary.allergenicity
        if value is not None and value > thresholds.max_allergenicity:
            return "allergenicity"

    length = row.get("peptide_length")
    if length is not None:
        if thresholds.min_peptide_length is not None and length < thresholds.min_peptide_length:
            return "peptide_length"
        if thresholds.max_peptide_length is not None and length > thresholds.max_peptide_length:
            return "peptide_length"

    return None


def unassessed_count(candidate: Any, thresholds: Thresholds) -> int:
    """How many of the thresholds could not judge this candidate.

    A candidate with no value for a threshold it is subject to is kept rather than dropped,
    and this counts those so the response can say how many rows the thresholds did not
    actually rule on.
    """
    assembled = candidate.assembled
    direction = candidate.row["direction"]
    count = 0

    floor = thresholds.functional_floor.get(direction)
    if floor is not None and floor_applies(direction) and assembled.functional_value is None:
        count += 1
    if thresholds.max_allergenicity is not None and assembled.supplementary.allergenicity is None:
        count += 1
    if thresholds.min_peptide_length is not None or thresholds.max_peptide_length is not None:
        if candidate.row.get("peptide_length") is None:
            count += 1
    return count


def reference() -> dict[str, Any]:
    """The threshold reference the interface needs before any build has run.

    Everything here is derived from the same place the thresholds are enforced, so the
    starting values the interface offers and the values the service applies cannot drift
    apart.
    """
    directions: dict[str, Any] = {}
    for direction in scoring.FUNCTIONAL_SCORE:
        tool_key, semantics = scoring.FUNCTIONAL_SCORE[direction]
        declared = scoring.functional_threshold(tool_key)
        applies = semantics == ScoreSemantics.probability
        if applies:
            note = (
                "The score is a probability, so a floor on it is meaningful."
                if declared is not None
                else "The score is a probability, so a floor on it is meaningful. The "
                     "predictor declares no boundary of its own."
            )
        else:
            note = (
                "The score orders candidates rather than measuring activity, so a floor on "
                "it has no meaning. Use the per-direction cap instead."
            )
        directions[direction] = {
            "tool": scoring.functional_label(tool_key),
            "tool_key": tool_key,
            "semantics": semantics.value if hasattr(semantics, "value") else str(semantics),
            "floor_applies": applies,
            "declared_boundary": declared.value if declared is not None else None,
            "higher_is_better": True,
            "note": note,
        }

    return {
        "functional_score": directions,
        "allergenicity": {
            "tool": "AlgPred2",
            "boundary": ALLERGENICITY_BOUNDARY,
            "higher_is_better": False,
            "note": (
                "The predicted allergenicity of the peptide. The lower the value the safer "
                "the peptide is, so the threshold is a ceiling rather than a floor."
            ),
        },
        "peptide_length": {
            "min": PEPTIDE_LENGTH_MIN,
            "max": PEPTIDE_LENGTH_MAX,
            "note": (
                "The residue count of the peptide on its own, before the scaffold and the "
                "linker are added."
            ),
        },
        "per_direction_limit": {
            "note": (
                "How many candidates each direction contributes to the ranking, counted "
                "within that direction's own order. This is the way to hold several "
                "directions at once without one of them filling the page."
            ),
        },
    }
