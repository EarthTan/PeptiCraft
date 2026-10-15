"""Why the linker library is listed in the order it is.

The Builder offers the whole curated library and the order it arrives in is also the order it
is displayed in, so that order is a statement about the entries whether or not anyone intended
one. It previously carried no statement at all: the repository sorted by `length, name`, which
put the three-residue entries first and `GPG` at the top of every visit, and the frontend then
took the first entry as the standing choice for a reader who clicked nothing. Nothing said GPG
was suitable — it was simply the shortest name-sorted entry — and the interface had no way to
say otherwise, because the linker library's own `priority_reason` column was never populated
and the curation source it was to be filled from no longer exists (see the note in
`repositories/linkers.py`).

This module supplies the missing judgement. It is a judgement about assembly, not a measurement,
and it says so: no predictor in the pipeline was run on a fusion, so nothing here claims that a
given linker makes a given peptide more active.

The order
---------
Ranked most suitable first, on four considerations that apply to every construct this platform
builds — a short functional peptide (11-30 aa) fused to a large structural protein (225-1071 aa)
and used topically.

1. *The peptide has to stay reachable.* A scaffold surface that is 16 to 65 times the peptide's
   length can mask the very region the peptide is there for. A linker has to hold the peptide
   out far enough that it keeps its own fold, and the scaffold's own self-assembly has to
   survive the fusion.
2. *Small side chains and a solvated segment do the least damage.* Glycine has no side chain to
   occlude a peptide or to pack against a scaffold; serine keeps an unstructured segment
   soluble. A Gly-Ser linker is also compositionally continuous with the scaffolds here — the
   silk clusters are Gly/Ala/Ser repeats and the collagens present a Gly/Pro-rich surface — so
   it disturbs their assembly least.
3. *Length is a trade, and the useful window is narrow.* Below about five residues the peptide
   has too little reach; past about ten, every added residue is unstructured surface that
   proteases in a wound or skin environment can cut and that the recombinant host still has to
   make. The library's 15-25 aa entries are therefore placed below the 5-10 aa ones.
4. *Rigidity is a specialist answer.* A rigid linker fixes the distance and the angle between
   the two domains and takes away the peptide's freedom to adjust its own conformation. That is
   the right answer when the geometry is the point, and the wrong default when the point is to
   present a peptide. The α-helical family (EAAAK repeats) is ordered by length within itself;
   the proline entries are placed last because they are both rigid and very short, and because
   proline-rich sequences are among the harder ones to express recombinantly.

What this order is not
----------------------
It is not per-construct. It is not adjusted for the application route, for the scaffold family,
or for the peptide's own sequence, and no experiment here has compared two linkers on one
fusion. Assigning a different default, or a per-route default, is a change to this one table.
"""
from __future__ import annotations

# Keyed by sequence rather than by id. `linker_library` constrains sequence to be unique, and
# the two id vocabularies in play do not agree: the curated library names entries `LK_GGGGS`
# while the local fixture calls the same molecule `LK_GS3`. Sequence is the physical identity
# and survives both.
_RECOMMENDATION: dict[str, tuple[int, str]] = {
    "GGGGS": (
        1,
        "The default. Glycine has no side chain to occlude the peptide or to pack against the "
        "scaffold, serine keeps the segment soluble, and five residues give a 11-30 aa peptide "
        "enough reach to fold on its own while leaving no long protease-accessible tail. Its "
        "composition is continuous with the Gly/Ala/Ser repeats of the silk clusters and with "
        "the Gly/Pro-rich surface of the collagens, so it is the least likely of the fifteen to "
        "disturb the scaffold's own self-assembly. It is also what the stored pipeline rows "
        "carry, so accepting the default reproduces the archived assembly instead of departing "
        "from it.",
    ),
    "GGGGSGGGGS": (
        2,
        "The same chemistry at twice the reach. Use it when the peptide's active region has to "
        "clear a large scaffold surface — the collagen clusters here run from 225 to 1071 "
        "residues and present a charged, sticky surface that can mask a short peptide — while "
        "keeping the peptide free to fold. This is the most widely used flexible-linker length "
        "in fusion constructs.",
    ),
    "KESGS": (
        3,
        "Flexible, with one internal K-E salt bridge. The charge pair makes the segment less "
        "likely to collapse back onto the scaffold and slightly more resistant to proteases than "
        "a pure Gly-Ser run. It sits below the neutral Gly-Ser entries for that reason: two "
        "charged residues next to the fusion are one more thing a peptide whose activity depends "
        "on local charge or on a hydrophobic patch has to tolerate.",
    ),
    "GGSGGSGGS": (
        4,
        "A smaller Gly-Gly-Ser period, three times over. The segment stays compact and adds "
        "little bulk while still separating the two domains, which suits a peptide that should "
        "sit close to the scaffold rather than far from it. The trade is a lower serine fraction "
        "than the GGGGS family: marginally less solubilising, marginally more prone to collapse.",
    ),
    "GGGGSGGGGSGGGGS": (
        5,
        "Flexible at fifteen residues. It still separates cleanly, but it has left the useful "
        "window: every residue past about ten adds unstructured surface for proteases to cut and "
        "mass for the recombinant host to make. Reach for it when the peptide must sit clearly "
        "outside a large scaffold, not as a default.",
    ),
    "GGGGSGGGGSGGGGSGGGGS": (
        6,
        "The same argument at twenty residues — more reach, more open surface, a higher "
        "expression cost. Reserved for a case where a steric clash would otherwise mask the "
        "peptide's site.",
    ),
    "GGGGSGGGGSGGGGSGGGGSGGGGS": (
        7,
        "The longest flexible linker in routine use, and close to the upper bound; beyond this "
        "length recombinant yield tends to fall. Justified only when the two domains have to be "
        "physically far apart.",
    ),
    "EAAAK": (
        8,
        "First of the rigid family. A single α-helical unit fixes the distance and the angle "
        "between the peptide and the scaffold, which is what you want when the geometry itself is "
        "the requirement — and not what you want when the peptide needs to adjust its own "
        "conformation to reach a target. Five residues is also a short leash for a large scaffold "
        "surface. The glutamate-lysine pair caps the helix and limits fraying.",
    ),
    "EAAAKEAAAKEAAAK": (
        9,
        "Rigid at fifteen residues, roughly 22 Å of fixed separation. Choose it to hold the "
        "peptide at a set distance rather than to let it move. A helix is compact and its salt "
        "bridges are buried, so it is less protease-accessible than a flexible segment of the "
        "same length; the cost is a peptide whose orientation is decided for it.",
    ),
    "EAAAKEAAAKEAAAKEAAAK": (
        10,
        "Rigid at twenty residues, for cases that need strong spatial isolation between the two "
        "folded parts over a distance a flexible linker of tolerable length cannot guarantee.",
    ),
    "EAAAKEAAAKEAAAKEAAAKEAAAK": (
        11,
        "The longest rigid α-helical linker in routine use — a five-turn helix. Worth noting "
        "that high helical propensity is generally well tolerated by E. coli, which is the one "
        "respect in which a long rigid linker is easier to produce than a long flexible one.",
    ),
    "AKEAAAKAAKEAAAKA": (
        12,
        "Rigid, with the salt bridges rearranged for a more stable helix than EAAAK repeats of "
        "similar length. It is the most conformationally restrictive entry in the library: the "
        "right tool for holding two domains apart under all conditions, and the least forgiving "
        "if the peptide needs any mobility at all.",
    ),
    "GPG": (
        13,
        "Not a default. Proline forces a tight β-turn, giving the two domains a fixed relative "
        "angle at minimal length — the classic answer when the geometry must be locked and the "
        "peptide must stay close to the scaffold. Three residues cannot lift a peptide clear of a "
        "large scaffold surface, and proline-rich sequences are among the harder ones to express "
        "recombinantly. One place it is the natural choice is a collagen fusion, where the "
        "scaffold's polyproline-II helix and a proline turn are conformationally related.",
    ),
    "SAP": (
        14,
        "The shortest rigid option after GPG: a proline kink with the least possible peptide "
        "burden, in use for tag fusions. It carries GPG's two limitations — too short to separate "
        "a peptide from a bulky scaffold, and proline-rich.",
    ),
    "PPPPP": (
        15,
        "A polyproline rod. Fully rigid, no inter-domain flexibility at all, and the hardest of "
        "the fifteen to produce recombinantly. Last because it offers least of what this platform "
        "needs: a peptide that stays active on the outside of a structural protein.",
    ),
}

# The table covers the curated library, which is what the interface offers. The six sample rows
# are not ranked: they were attached to stored constructs by "take the first available row"
# rather than chosen, and giving one of them a position here would present that accident as a
# recommendation.
RANKED_TABLE = "linker_library"


def rank_for(sequence: str | None, source_table: str | None = None) -> int | None:
    """Where one entry sits in the recommendation, or None if it is not ranked."""
    if source_table is not None and source_table != RANKED_TABLE:
        return None
    entry = _RECOMMENDATION.get((sequence or "").strip().upper())
    return entry[0] if entry else None


def reason_for(sequence: str | None, source_table: str | None = None) -> str | None:
    """Why one entry sits where it does. Empty when nothing ranks it."""
    if source_table is not None and source_table != RANKED_TABLE:
        return None
    entry = _RECOMMENDATION.get((sequence or "").strip().upper())
    return entry[1] if entry else None
