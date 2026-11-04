"""The Builder's response models — a build performed now rather than a stored construct.

`GET /api/constructs` answers what has been stored. The Builder asks a different question:
given a route, a set of directions, a scaffold and a linker, what do the candidates become.
The difference is not cosmetic. A stored construct carries whichever scaffold and linker the
pipeline recorded; a build is assembled against the ones the caller names, and the fused
sequence that results is the whole point of the page. Serving both from one shape would mean
putting a fused sequence on every library row, where it answers nothing.

Three consequences are visible in the shapes below.

A candidate is a top-channel row. The bottom channel is the negative-control arm — real rows
with real scores, seeded so a comparison has a baseline — so a build filters it out rather
than ranking a control marker against the candidates.

The ranking is computed over the whole candidate set and sliced afterwards. A row's composite
is a function of its direction's pool, which is read independently of the request, so the
value does not move when the request is narrowed; ordering everything and then slicing is
therefore both correct and affordable at a few hundred rows per direction. It also makes
`offset` mean something, which sorting a single page inside the browser never did.

The scaffold's provenance and the linker's are reported separately, because they are
answered separately. A build can take its scaffold from the record and its linker from the
request, and either choice changes the fused sequence without touching the scores.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .catalog import DeliveryRoute
from .construct import ConstructSummary, SequenceSegment
from .linker import LinkerView
from .scaffold import ScaffoldSummary


class BuiltConstruct(ConstructSummary):
    """One candidate, assembled against the scaffold and linker the build used.

    Everything on `ConstructSummary` still holds, with one change of meaning: `backbone_name`,
    `backbone_binding` and `linker_name` describe what this build assembled the row with,
    which is the caller's choice for whichever of the two was named and the row's stored value
    otherwise.
    """

    full_sequence: str | None = Field(
        default=None,
        description="Backbone + linker + peptide, concatenated. Null when any of the three "
        "segments has no known sequence — which happens for a row whose stored binding is a "
        "placeholder and for which the build named no scaffold. A two-part string is never "
        "emitted under this field, because it reads as a construct sequence.",
    )
    fused_length: int | None = Field(
        default=None,
        description="Residue count of `full_sequence`. Carried separately so a caller does "
        "not have to re-derive it, and so the difference between it and `peptide_length` is "
        "visible at a glance — that difference is the scaffold and linker the build added.",
    )
    assembled_sequence_available: bool = Field(
        default=False,
        description="False when no fused sequence could be emitted for this row. Rows in one "
        "response can disagree: a build with no scaffold named inherits each row's stored "
        "binding, and a mix of verified and placeholder rows is a normal outcome.",
    )
    segments: list[SequenceSegment] = Field(
        default_factory=list,
        description="The same three-part breakdown the construct detail page renders, so a "
        "candidate can show its assembly without a second request.",
    )
    allergenicity: float | None = Field(
        default=None,
        description="The AlgPred2 allergenicity score. It is carried on the row because it is "
        "one of the values a screening threshold compares, and a threshold can only be applied "
        "where the number it compares is present.",
    )


class BuildCounts(BaseModel):
    """Verdict tally over every candidate the build matched, before `limit` is applied.

    Taken over the whole match rather than over the returned page. A tally over a page reads
    as a property of the candidate set while actually describing where the slice happened to
    fall, which is the figure the page previously could not help but show.
    """

    clear: int = 0
    borderline: int = 0
    vetoed: int = 0
    indeterminate: int = 0
    ranked: int = Field(
        description="How many candidates the tally covers: the whole match, not `len(items)`."
    )
    without_composite: int = Field(
        default=0,
        description="Candidates carrying no composite under this route. They are sorted last "
        "rather than treated as zero, and they are the rows to look at when a direction "
        "returns fewer usable rankings than it has candidates.",
    )


class DirectionThresholdOutcome(BaseModel):
    """What one direction's thresholds did to its own candidates.

    Reported per direction rather than as one total, because a threshold set on one
    direction cannot affect another: the score floors are per direction by construction, and
    the peptide length and allergenicity ceilings happen to be the same everywhere but are
    still counted where they land.
    """

    direction: str
    pool: int = Field(
        description="Candidates this direction held before any threshold was applied."
    )
    kept: int = Field(
        description="Candidates this direction contributes after every threshold, including "
        "the per-direction cap."
    )
    removed_by_threshold: int = Field(
        default=0,
        description="Candidates a threshold ruled out.",
    )
    removed_by_cap: int = Field(
        default=0,
        description="Candidates the per-direction cap ruled out.",
    )
    unassessed: int = Field(
        default=0,
        description="Candidates a threshold could not judge, because the value it would have "
        "compared was not measured. They are kept rather than dropped.",
    )
    functional_score_floor: float | None = Field(
        default=None,
        description="The score floor that was asked for on this direction.",
    )
    functional_score_floor_applied: bool = Field(
        default=False,
        description="Whether the floor was applied. False when the direction's score is a "
        "ranking signal rather than a probability, in which case the floor was not applied "
        "and the request says so.",
    )
    note: str | None = Field(
        default=None,
        description="Why a requested threshold was not applied, when it was not.",
    )


class BuildThresholds(BaseModel):
    """The screening thresholds the build ran under, and what they removed.

    Absent thresholds are null rather than zero, so a response says "no allergenicity
    ceiling was set" instead of "the ceiling was zero", which would exclude every candidate.
    """

    functional_score_floor: dict[str, float] = Field(
        default_factory=dict,
        description="The score floor asked for on each direction.",
    )
    max_allergenicity: float | None = None
    min_peptide_length: int | None = None
    max_peptide_length: int | None = None
    per_direction_limit: int | None = None
    removed: int = Field(
        default=0,
        description="Candidates the thresholds ruled out, before the per-direction cap.",
    )
    removed_by_cap: int = Field(
        default=0,
        description="Candidates the per-direction cap ruled out.",
    )
    directions: list[DirectionThresholdOutcome] = Field(default_factory=list)


class BuildResult(BaseModel):
    """A build: the choices it was made under, the ranking, and the tally behind it."""

    route: DeliveryRoute
    scaffold: ScaffoldSummary | None = Field(
        default=None,
        description="The scaffold the build assembled against. Null when the caller named "
        "none, in which case each row fell back to its stored binding.",
    )
    linker: LinkerView | None = Field(
        default=None,
        description="The linker the build assembled every candidate with. Null when the "
        "caller named none, in which case each row fell back to the linker its own stored "
        "row records and the rows can differ. `source_table` on it says which of the two "
        "linker tables the sequence came from.",
    )
    binding_note: str = Field(
        description="Prose stating where the scaffold assignment came from. Present because "
        "an assembled sequence is not evidence of a recorded one: a build reproduces a real "
        "scaffold with a real linker and peptide, but the pairing is the caller's choice."
    )
    linker_note: str = Field(
        description="Where the linker came from, stated separately from the scaffold's "
        "account because the two can be answered differently in one build. A build that "
        "names a linker changes the sequence every candidate is assembled into and nothing "
        "else: the candidate set, the scores and the ranking are unaffected."
    )
    scope_note: str = Field(
        description="What the assembled sequence does and does not support. The nine scores "
        "beside each candidate describe the functional peptide alone; no predictor in the "
        "pipeline was run on the fusion protein."
    )
    directions: list[str] = Field(description="The directions the build covered, in order.")
    totals: dict[str, int] = Field(
        description="Candidates matched per direction, before `limit`. With no threshold set "
        "this is the direction's whole candidate set; with thresholds it is what survived "
        "them, and `thresholds.directions` carries the pool each direction started from. A "
        "requested direction with no stored candidate appears here as 0 rather than being "
        "omitted, so a caller can tell 'nothing stored' from 'not asked for'."
    )
    total: int = Field(description="Sum of `totals`: the size of the ranking that was sliced.")
    counts: BuildCounts
    thresholds: BuildThresholds = Field(
        default_factory=BuildThresholds,
        description="The screening thresholds the build ran under and what each of them "
        "removed. With no threshold set this reports that nothing was ruled out.",
    )
    items: list[BuiltConstruct]
    limit: int
    offset: int
