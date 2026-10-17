"""Analysis text generation.

The generator is a protocol, not a function, so that a model-backed implementation can be
added later without the router, the response model or the frontend changing.

`TemplateGenerator` is the implementation registered today. It reads the construct's real
scores, the route's thresholds and the peptide's own attributes, and composes prose from
them. Determinism is the point: the same construct under the same route always renders the
same text, and every number in that text appears as a field in the same response, so a
reader can check any claim without running a query.

This replaces `app/src/data/chat.ts`, a 453-line module of fixed strings that was never
referenced by any page and had drifted well past the data — it still advertised a 32-linker
library, a 1,760 Da figure and "8 rounds of screening" long after the platform carried 15
linkers, no molecular-weight figure and four rounds.

`provider` travels on every response, and it names the generator that produced *that* answer.
The distinction matters because a model-backed generator can fail: when it does, the answer
falls back to the template's, and the response has to say so. That decision is made in
`chat` — one place, so the label and the text cannot disagree — rather than inside the
generator, which would leave the label saying `llm` over the template's own prose.

This replaces `app/src/data/chat.ts`, a 453-line module of fixed strings that was never
referenced by any page and had drifted well past the data — it still advertised a 32-linker
library, a 1,760 Da figure and "8 rounds of screening" long after the platform carried 15
linkers, no molecular-weight figure and four rounds.
"""
from __future__ import annotations

import inspect
import logging
import uuid
from datetime import datetime, timezone
from typing import Protocol

from ..models.analysis import AnalysisBlock, ChatMessage, ChatResponse, ExpressionPlan
from ..models.common import BackboneBinding, ScoreSemantics
from ..models.construct import ConstructDetail
from . import reference

log = logging.getLogger("pepticraft.analysis")

PROVIDER_TEMPLATE = "template"
PROVIDER_LLM = "llm"


class ModelUnavailable(RuntimeError):
    """Raised by a model-backed generator that could not produce an answer.

    Defined here rather than in the module that raises it so there is no import cycle —
    `llm` imports this module, not the other way round — and so the generator protocol and
    its failure mode are stated together.
    """


class AnalysisGenerator(Protocol):
    """Implemented by the template generator and by the model-backed one.

    `answer` takes the conversation so far. The template ignores it — it answers from the
    record, and there is nothing in a previous turn that changes what the record says — while a
    model-backed generator needs it to resolve a question like "and the one above it". The
    parameter is keyword-only with a default so a generator that does not need it can declare
    `answer(self, construct, question)` and still satisfy the protocol.

    `answer` raises `ModelUnavailable` when the generator cannot answer at all. A generator
    that always can — the template — never raises it.
    """

    name: str

    def blocks(self, construct: ConstructDetail) -> list[AnalysisBlock]: ...

    def answer(
        self, construct: ConstructDetail, question: str, *, history: list[dict[str, str]] | None = None
    ) -> str: ...


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _pct(value: float | None) -> str:
    return "not assessed" if value is None else f"{value:.3f}"


def _verdict_word(verdict: str) -> str:
    return {
        "clear": "clears every assessed gate",
        "vetoed": "is stopped by a veto gate",
        "borderline": "clears every assessed gate but sits close to one",
        "indeterminate": "has no assessed veto gate and cannot be cleared or stopped",
    }.get(verdict, verdict)


def _route_name(route_id: str | None) -> str:
    route = reference.ROUTES_BY_ID.get(route_id or "")
    return route.name if route else "the selected route"


# The `antioxidant` slot of the nine-score grid holds whichever predictor ranks the
# construct's direction. The name is a leftover from a single-direction platform.
_FUNCTIONAL_SLOT = "antioxidant"


def _source_phrase(source: str) -> str:
    """How a threshold's origin reads inside a sentence.

    The service carries `tool` / `route` / `project` as tokens, which is right for a field
    and wrong for prose: "a threshold of 0.380 from tool" is not a sentence.
    """
    return {
        "tool": "the predictor's own cut-off",
        "route": "the route's screening profile",
        "project": "a platform-wide constant",
    }.get(source, source)


# Side-chain pKa values for the residues that carry a charge near neutral pH. Everything not
# listed is treated as neutral, which is right for the twenty-proteinogenic set apart from the
# termini handled below.
_PKA = {"D": 3.65, "E": 4.25, "C": 8.18, "Y": 10.07, "H": 6.00, "K": 10.53, "R": 12.50}
_N_TERMINUS_PKA = 9.69
_C_TERMINUS_PKA = 2.34


def _net_charge(seq: str, ph: float = 7.0) -> float:
    """Net charge in proton units at a given pH, by Henderson-Hasselbalch.

    Not a predictor and not part of the nine-score contract: it is arithmetic on the peptide's
    own sequence, used only to decide whether a construct belongs to the cationic class that
    stresses an E. coli envelope. Stated here so the threshold it feeds has a visible basis
    rather than an assertion.
    """
    charge = 0.0
    for aa in seq:
        pka = _PKA.get(aa)
        if pka is None:
            continue
        if aa in "KRH":
            charge += 1.0 / (1.0 + 10 ** (ph - pka))
        else:
            charge -= 1.0 / (1.0 + 10 ** (pka - ph))
    charge += 1.0 / (1.0 + 10 ** (ph - _N_TERMINUS_PKA))
    charge -= 1.0 / (1.0 + 10 ** (_C_TERMINUS_PKA - ph))
    return charge


def _hydrophobic_fraction(seq: str) -> float:
    hydrophobic = set("AVILMFWY")
    return sum(1 for a in seq if a in hydrophobic) / len(seq) if seq else 0.0


# The solubility below which the standard induction is expected to lose product to inclusion
# bodies. It is the platform's own planning cut: SoDoPE returns a 0-1 score and publishes no
# threshold, so the number is stated here once instead of being implied by a branch.
SOLUBILITY_STANDARD_CUT = 0.45

# The carrier length beyond which a collagen repeat is recommended into a eukaryotic host. The
# scaffold library's collagen entries are 225-1071 aa and only the longest crosses this, so the
# cut separates the one case that needs hydroxylation from the four that do not.
COLLAGEN_ECOLI_LIMIT = 600

# The net charge at which a peptide is treated as cationic enough to stress the envelope.
CATIONIC_CHARGE = 3.5


# ---------------------------------------------------------------------------
# Template implementation
# ---------------------------------------------------------------------------

class TemplateGenerator:
    name = PROVIDER_TEMPLATE

    def blocks(self, c: ConstructDetail) -> list[AnalysisBlock]:
        return [
            self._safety(c),
            self._peptide_origin(c),
            self._linker_rationale(c),
            self._expression_strategy(c),
            self._comparison(c),
            self._risk(c),
        ]

    # -- block 1 ------------------------------------------------------------
    def _safety(self, c: ConstructDetail) -> AnalysisBlock:
        gates = c.safety.gates
        # Which gates eliminate is read off the gate itself. Restating the key list here put
        # the rule in two places, and the two had already drifted apart once.
        veto = [g for g in gates if g.is_veto_gate]
        lines = [
            f"Under the {_route_name(c.safety.route_id)} profile, this construct "
            f"{_verdict_word(c.safety.verdict)}."
        ]

        for g in veto:
            if g.value is None:
                lines.append(
                    f"{g.label} has no measured value, so it is reported as not assessed "
                    f"rather than as a pass. The pipeline's rule is that an unassessed metric "
                    f"does not eliminate a candidate."
                )
            else:
                # The failing side depends on the metric. Most gates fail on a high value;
                # the MHC-II percent rank fails on a low one, because a low percent rank is
                # a stronger binder.
                if g.higher_is_better:
                    side = "at or above" if g.passed else "below"
                else:
                    side = "at or below" if g.passed else "above"
                lines.append(
                    f"{g.label} ({g.tool}) measures {_pct(g.value)} against a threshold of "
                    f"{_pct(g.threshold)} from {_source_phrase(g.threshold_source)}, which is "
                    f"{side} the limit."
                    + (" The value sits within ten percent of the threshold." if g.borderline else "")
                )

        soft = [g for g in gates if not g.is_veto_gate]
        if soft:
            assessed_soft = [g for g in soft if g.value is not None]
            if assessed_soft:
                lines.append(
                    "Soft signals, which do not veto: "
                    + "; ".join(
                        f"{g.label} {_pct(g.value)}"
                        + (f" (threshold {_pct(g.threshold)})" if g.threshold else "")
                        for g in assessed_soft
                    )
                    + "."
                )

        if c.safety.verdict == "vetoed":
            lines.append(
                "Because the pipeline applies no weighted compensation to veto gates, a "
                "single failure removes the candidate outright."
            )

        return AnalysisBlock(
            id="safety",
            type="safety",
            title="Safety reading",
            icon="shield",
            content="\n".join(lines),
            citations=[
                "safety.verdict",
                "safety.gates[].value",
                "safety.gates[].threshold",
                "safety.immunogenicity_threshold",
            ],
        )

    # -- block 2 ------------------------------------------------------------
    def _peptide_origin(self, c: ConstructDetail) -> AnalysisBlock:
        p = c.peptide
        seq = p.sequence
        length = len(seq)

        hydrophobic = set("AVILMFWY")
        charged = set("DEKRH")
        aromatic = set("FWY")
        cys = seq.count("C")

        hyd = sum(1 for a in seq if a in hydrophobic)
        chg = sum(1 for a in seq if a in charged)
        arom = sum(1 for a in seq if a in aromatic)

        lines = [
            f"The peptide is {length} residues, drawn from {p.source} "
            f"(dataset version {p.source_version}).",
            f"Composition: {hyd} hydrophobic residues ({hyd / length:.0%}), "
            f"{chg} charged ({chg / length:.0%}), {arom} aromatic ({arom / length:.0%}).",
        ]

        if cys:
            lines.append(
                f"{cys} cysteine residue{'s' if cys > 1 else ''} present, which allows "
                f"disulfide formation and can stiffen the peptide against proteolysis."
            )
        else:
            lines.append(
                "No cysteine residues, so the peptide has no disulfide-mediated structural "
                "constraint."
            )

        if c.supplementary.aggregation_a3v is not None:
            agg = c.supplementary.aggregation_a3v
            reading = (
                "below zero, which indicates a low intrinsic aggregation propensity"
                if agg < 0
                else "above zero, which indicates some aggregation propensity"
            )
            lines.append(
                f"One-dimensional AGGRESCAN gives {agg:.3f}, {reading}. The scale is a mean "
                f"per-residue aggregation score, negative for aggregation-averse sequences."
            )

        # The predictor is named from the score grid's own metadata. This block used to hold a
        # third hand-written key-to-name table, and it was both incomplete and wrong: the
        # antibacterial key is `amp-esm`, which the table did not carry, so the sentence read
        # "The functional score of 0.848 is amp-esm from amp-esm."
        func_meta = c.score_meta.get(_FUNCTIONAL_SLOT)
        predictor = func_meta.tool if func_meta else c.functional_score_label
        lines.append(
            f"The direction's functional score is {_pct(c.functional_score)}, produced by "
            f"{predictor or c.functional_score_key}."
        )
        if c.semantics == ScoreSemantics.ranking_only:
            lines.append(
                "That score is a ranking signal, not a probability. It separates "
                "functional-looking peptides from random fragments rather than measuring "
                "activity, so it is used for ordering only."
            )

        return AnalysisBlock(
            id="peptide_origin",
            type="peptide_origin",
            title="Peptide origin and composition",
            icon="dna",
            content="\n".join(lines),
            citations=[
                "peptide.sequence",
                "peptide.source",
                "peptide.source_version",
                "supplementary.aggregation_a3v",
                "functional_score",
            ],
        )

    # -- block 3 ------------------------------------------------------------
    def _linker_rationale(self, c: ConstructDetail) -> AnalysisBlock:
        lines = []
        if c.linker is None:
            lines.append("No linker is recorded for this construct.")
        else:
            lk = c.linker
            lines.append(
                f"The linker is {lk.name}, {lk.length} residues long, classified as "
                f"{lk.rigidity}."
            )
            lines.append(
                "A glycine-serine linker of this kind gives the fused peptide rotational "
                "freedom and separates it from the scaffold surface, which matters when the "
                "functional epitope would otherwise be masked by the scaffold. The trade-off "
                "is that the unstructured segment is more exposed to proteases."
            )
            lines.append(
                "The linker sequence recorded here comes from the sample linker table rather "
                "than the curated library, and the construct carries no verified linker "
                "choice: the assembly step that produced it picked the first available row."
            )

        # The three binding states read differently, and saying "named at request time" for a
        # verified stored binding would be a factual error: the scaffold came from the
        # construct's own row.
        if not c.assembled_sequence_available:
            assembly_reading = (
                "No fused sequence is emitted, because the bound scaffold row holds a marker "
                "string rather than a real sequence."
            )
        elif c.backbone_binding == BackboneBinding.verified:
            assembly_reading = (
                "A fused sequence is emitted, assembled from the scaffold sequence recorded "
                "against this construct."
            )
        else:
            assembly_reading = (
                "A fused sequence is emitted, using a scaffold named at request time."
            )

        lines.append(
            f"The construct's stored scaffold binding is `{c.backbone_binding}`. "
            + assembly_reading
        )

        return AnalysisBlock(
            id="linker_rationale",
            type="linker_rationale",
            title="Linker and assembly",
            icon="link",
            content="\n".join(lines),
            citations=["linker.name", "linker.length", "linker.rigidity", "backbone_binding"],
        )

    # -- block 4 ------------------------------------------------------------
    def _expression_plan(self, c: ConstructDetail) -> ExpressionPlan:
        """Choose a host, vector and induction regime from properties the record holds.

        The dataset carries no expression condition for any construct — `backbone_proteins`
        has no such column and `scaffold_patients`' experiment table is not read by the
        service — so a block that only said "nothing is recorded here" left the reader with
        nothing to act on. What can be derived without inventing data is the standard route
        for the peptide's own properties, and the one switch that matters for a carrier:
        repeat-rich collagen above `COLLAGEN_ECOLI_LIMIT` needs a eukaryotic host.

        Every branch is a rule about a field in the same response, and the prose below names
        the rule. Nothing here claims an experimental outcome: solubility and thermal
        stability are used to pick between published expression regimes, not to predict a
        yield.
        """
        seq = c.peptide.sequence
        hydro = _hydrophobic_fraction(seq)
        charge = _net_charge(seq)
        cys = seq.count("C")
        sol = c.scores.solubility
        scaffold = c.scaffold

        if (
            scaffold is not None
            and scaffold.category == "recombinant-collagen"
            and (scaffold.length or 0) > COLLAGEN_ECOLI_LIMIT
        ):
            return ExpressionPlan(
                host="Pichia pastoris (Komagataella phaffii)",
                strain="X-33",
                vector="pPICZα-A",
                tag="a C-terminal His6 tag, encoded by the vector",
                induction="1% methanol, replenished every 24 h",
                temperature_c=28,
                duration_h="72–96",
                purification="secreted into the medium — Ni-NTA from clarified supernatant, "
                "then size exclusion",
                tier="secretion",
            )

        # A repeat-rich carrier recombines in a recA+ host, and BL21 is not recA-deficient
        # while HMS174 is. Only a bound scaffold says the carrier is one of those classes,
        # which is why the unbound default stays BL21 rather than pre-emptively hardening.
        repeat_carrier = scaffold is not None and scaffold.category in {
            "spider-silk",
            "silkworm-silk",
            "recombinant-collagen",
        }
        if cys >= 2:
            strain = "SHuffle T7"
        elif repeat_carrier:
            strain = "HMS174(DE3)"
        else:
            strain = "BL21(DE3)"

        if (sol is not None and sol < SOLUBILITY_STANDARD_CUT) or hydro >= 0.5:
            return ExpressionPlan(
                host="Escherichia coli",
                strain=strain,
                vector="pET SUMO",
                tag="an N-terminal His6-SUMO tag, cleaved with Ulp1 after capture",
                induction="0.2 mM IPTG at OD600 0.6–0.8",
                temperature_c=16,
                duration_h="18–20",
                purification="Ni-NTA capture, Ulp1 cleavage, then size exclusion",
                tier="solubility-rescue",
            )

        if charge >= CATIONIC_CHARGE:
            return ExpressionPlan(
                host="Escherichia coli",
                strain=strain,
                vector="pET-28a(+)",
                tag="an N-terminal His6 tag",
                induction="0.4 mM IPTG at OD600 0.4–0.5",
                temperature_c=22,
                duration_h="12–16",
                purification="Ni-NTA, then size exclusion",
                tier="tight-control",
            )

        return ExpressionPlan(
            host="Escherichia coli",
            strain=strain,
            vector="pET-28a(+)",
            tag="an N-terminal His6 tag",
            induction="0.4 mM IPTG at OD600 0.6–0.8",
            temperature_c=25,
            duration_h="6",
            purification="Ni-NTA, then size exclusion",
            tier="standard",
        )

    def _expression_strategy(self, c: ConstructDetail) -> AnalysisBlock:
        seq = c.peptide.sequence
        plan = self._expression_plan(c)
        sol = c.scores.solubility
        hydro = _hydrophobic_fraction(seq)
        charge = _net_charge(seq)
        cys = seq.count("C")
        scaffold = c.scaffold

        lines = [
            f"Recommended route: {plan.host}, strain {plan.strain}, {plan.vector} with "
            f"{plan.tag}.",
            f"Induction: {plan.induction}, {plan.temperature_c} °C, {plan.duration_h} h. "
            f"Purification: {plan.purification}.",
            "This is a recommendation rather than a stored condition: the dataset records no "
            "expression host, vector or induction condition for any construct. It is derived "
            "from the peptide's predicted properties, its composition, and — where one is "
            "bound — the scaffold's class.",
        ]

        if plan.tier == "secretion":
            described = (
                f"a recombinant-collagen entry of {scaffold.length} residues"
                if scaffold.length
                else "a recombinant-collagen entry of unstated length"
            )
            lines.append(
                f"The bound scaffold is {scaffold.short_name}, {described}. A repeat at that "
                f"length needs prolyl hydroxylation to form a stable triple helix, and a "
                f"bacterial host has no prolyl hydroxylase, so the gene is put into a secreted "
                f"yeast host instead. The trade-off is time: 72–96 h of methanol induction "
                f"against a day in E. coli."
            )
        elif plan.tier == "solubility-rescue":
            below_cut = sol is not None and sol < SOLUBILITY_STANDARD_CUT
            greasy = hydro >= 0.5
            if below_cut and greasy:
                opening = (
                    f"Two properties point the same way. Predicted solubility is {_pct(sol)} "
                    f"(SoDoPE), under the 0.45 planning cut used here, and {hydro:.0%} of the "
                    f"peptide's residues are hydrophobic, which is the composition that drives "
                    f"inclusion-body formation."
                )
            elif below_cut:
                opening = (
                    f"Predicted solubility is {_pct(sol)} (SoDoPE), under the 0.45 planning cut "
                    f"used here."
                )
            else:
                opening = (
                    f"{hydro:.0%} of the peptide's residues are hydrophobic, which is the "
                    f"composition that drives inclusion-body formation."
                )
            lines.append(
                opening + " The route therefore adds a His6-SUMO fusion and drops induction to "
                "16 °C: the fusion partner keeps the peptide from collapsing into inclusion "
                "bodies, and the lower temperature slows aggregation faster than it slows "
                "expression. The cost is one cleavage step and a second chromatography run."
            )
        elif plan.tier == "tight-control":
            lines.append(
                f"The peptide carries a net charge of +{charge:.1f} at pH 7.0, which is the "
                f"cationic range that stresses an E. coli envelope and selects for plasmid loss. "
                f"Induction is therefore held to a low cell density at 22 °C: the culture "
                f"spends less time expressing a product that damages the membrane it is made "
                f"in. If transformants grow poorly or the plasmid is lost anyway, the same "
                f"gene in a secreted yeast host is the next step."
            )
        else:
            if sol is None:
                lines.append(
                    "Solubility was not assessed for this peptide, so the route stays at the "
                    "standard setting rather than adding a fusion partner on no evidence. If a "
                    "SoDoPE value is later scored below 0.45, the solubility-rescue route "
                    "replaces this one."
                )
            else:
                lines.append(
                    f"Predicted solubility is {_pct(sol)} (SoDoPE), at or above the 0.45 "
                    f"planning cut used here, so no solubility tag is added and the standard "
                    f"25 °C induction is kept. The peptide is {len(seq)} residues, short enough "
                    f"that its own folding is not the limiting step; what the yield then depends "
                    f"on is how the carrier behaves."
                )

        if cys >= 2:
            lines.append(
                f"The peptide has {cys} cysteines, so the host is {plan.strain}: an oxidative "
                f"cytoplasm lets the disulfide close without a refolding step."
            )
        elif cys == 1:
            lines.append(
                "One cysteine is present, which cannot form an intrachain disulfide on its "
                "own and instead cross-links neighbouring molecules on storage. A reducing "
                "agent is kept in the buffer until the final step."
            )

        if c.scores.thermal_stability is not None:
            lines.append(
                f"Predicted thermal stability is {_pct(c.scores.thermal_stability)} "
                f"(TemStaPro). It does not enter the host choice; it bears on storage "
                f"temperature and on any heating step after purification."
            )

        if scaffold is None:
            lines.append(
                "No scaffold is bound to this construct — the stored binding is a placeholder "
                "— so the carrier sequence and the construct's total length are unknown, and "
                "the host stays at the E. coli default. Binding a library scaffold moves the "
                "route to P. pastoris when that scaffold is a recombinant-collagen fragment "
                "longer than 600 residues, and to a recA-deficient strain when it is a "
                "repeat-rich silk or collagen."
            )
            if not c.assembled_sequence_available:
                lines.append(
                    "With no fused sequence on the record, a synthetic gene cannot be ordered "
                    "until that binding is filled in; the route above describes what to do once "
                    "it is."
                )
        elif scaffold.category in ("spider-silk", "silkworm-silk"):
            described = (
                f"a {scaffold.category.replace('-', ' ')} entry of {scaffold.length} residues"
                if scaffold.length
                else f"a {scaffold.category.replace('-', ' ')} entry of unstated length"
            )
            lines.append(
                f"The bound scaffold is {scaffold.short_name}, {described}. Its repeats are "
                f"what put the gene at risk of rearrangement, which is why the strain is "
                f"recA-deficient rather than the usual BL21."
            )
        elif scaffold.category == "recombinant-collagen":
            described = (
                f"a recombinant-collagen entry of {scaffold.length} residues"
                if scaffold.length
                else "a recombinant-collagen entry of unstated length"
            )
            lines.append(
                f"The bound scaffold is {scaffold.short_name}, {described}. At that length the "
                f"repeat is short enough to keep in E. coli, and the strain is recA-deficient "
                f"so it does not rearrange during propagation. A bacterial host cannot "
                f"hydroxylate the prolines of a triple helix, which is the standing limitation "
                f"of expressing any collagen fragment this way."
            )

        return AnalysisBlock(
            id="expression_strategy",
            type="expression_strategy",
            title="Expression and handling",
            icon="flask",
            content="\n".join(lines),
            plan=plan,
            citations=[
                "peptide.sequence",
                "scores.solubility",
                "scores.thermal_stability",
                "scaffold.category",
                "scaffold.length",
            ],
        )

    # -- block 5 ------------------------------------------------------------
    def _comparison(self, c: ConstructDetail) -> AnalysisBlock:
        rows = _direction_peers(c.direction, limit=5)
        lines = [
            f"Peers within the {c.direction_label} direction, ordered by composite under "
            f"{_route_name(c.safety.route_id)}. The composite is a ranking score computed "
            f"from developability components, so a higher value means a better combination "
            f"of penetration, solubility and thermal stability rather than stronger activity."
        ]
        for i, peer in enumerate(rows, 1):
            marker = " ← this construct" if peer["id"] == c.id else ""
            lines.append(
                f"{i}. {peer['name']} — composite {_pct(peer['composite'])}, "
                f"functional {_pct(peer['functional_score'])}, "
                f"toxicity {_pct(peer['toxicity'])}, haemolysis {_pct(peer['hemolysis'])}{marker}"
            )
        return AnalysisBlock(
            id="comparison",
            type="comparison",
            title="Comparison within the direction",
            icon="bar-chart",
            content="\n".join(lines),
            citations=["composite", "functional_score", "scores.toxicity", "scores.hemolysis"],
        )

    # -- block 6 ------------------------------------------------------------
    def _risk(self, c: ConstructDetail) -> AnalysisBlock:
        lines = []
        if c.unassessed_metrics:
            lines.append(
                "Not assessed for this construct: " + ", ".join(c.unassessed_metrics) + "."
            )
        else:
            lines.append("Every metric in the nine-score contract has a measured value.")

        if c.safety.unassessed:
            lines.append(
                "Veto gates without a measurement: " + ", ".join(c.safety.unassessed)
                + ". These are reported as unassessed rather than as passing."
            )

        if not c.assembled_sequence_available:
            lines.append(
                "No fused sequence is available, because the scaffold binding is a "
                "placeholder. Any downstream step that needs the full construct sequence "
                "cannot proceed on this record."
            )

        if c.status == "WIP":
            lines.append(
                "The construct carries the status WIP. Its direction has not been signed off, "
                "so its rank should not be read as a settled ordering."
            )

        if c.channel == "bottom":
            lines.append(
                "This construct sits in the bottom channel, which exists as a negative "
                "control for comparison rather than as a candidate."
            )

        return AnalysisBlock(
            id="risk",
            type="risk",
            title="Risk register",
            icon="alert",
            content="\n".join(lines),
            citations=["unassessed_metrics", "safety.unassessed", "status", "channel"],
        )

    # -- chat ---------------------------------------------------------------
    def answer(
        self,
        c: ConstructDetail,
        question: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        # `history` is accepted and unused. A template answers from the record, so a previous
        # turn cannot change what the record says; the parameter exists so the model-backed
        # generator can be dropped in without a request-shape change.
        q = question.lower().strip()

        if any(w in q for w in ("safe", "safety", "tox", "hemo", "immun", "gate")):
            return self._safety(c).content
        if any(w in q for w in ("sequence", "assembl", "backbone", "scaffold", "fuse")):
            return self._linker_rationale(c).content
        if any(w in q for w in ("solubility", "express", "purif", "yield", "stability", "thermal")):
            return self._expression_strategy(c).content
        if any(w in q for w in ("origin", "source", "composit", "peptide")):
            return self._peptide_origin(c).content
        if any(w in q for w in ("compare", "rank", "best", "peer", "composite")):
            return self._comparison(c).content
        if any(w in q for w in ("risk", "caveat", "unassess", "missing", "limit")):
            return self._risk(c).content

        return (
            f"This answer is generated from the record for {c.name} rather than from a "
            f"language model, so it covers the fields the record actually holds. Available "
            f"topics: the safety gates and the route's immunogenicity threshold; the peptide's "
            f"origin and composition; the linker and the state of the scaffold binding; "
            f"solubility and thermal stability; the comparison with peers in the same "
            f"direction; and the construct's unassessed metrics. "
            f"Current composite under {_route_name(c.safety.route_id)}: {_pct(c.composite)}."
        )

    def suggested_questions(self, c: ConstructDetail) -> list[str]:
        out = [
            "How does the safety gate read under this route?",
            "Which metrics were not assessed?",
            "What is the state of the scaffold binding?",
            "What expression route is recommended?",
        ]
        if c.semantics == ScoreSemantics.ranking_only:
            out.append("Why is the functional score a ranking signal rather than a probability?")
        return out


def _direction_peers(direction: str, limit: int = 5) -> list[dict]:
    """Top constructs of the same direction, for the comparison block.

    Runs the same computation the detail response uses, so a peer row cannot disagree with
    that construct's own page about a score.

    Imported lazily: the analysis service is constructed by the router, and importing the
    construct service at module scope would close a cycle between the two.
    """
    from ..repositories import constructs as repo
    from . import constructs as construct_service

    rows, _ = repo.list_constructs(direction=direction, channel="top", limit=limit, offset=0)
    if not rows:
        return []
    enriched = construct_service.load_enrichment(rows)
    out = []
    for row in rows:
        a = construct_service.compute(row, enriched.get(row["peptide_id"], {}), None)
        out.append({
            "id": construct_service.public_id(row["id"]),
            "name": construct_service.public_id(row["id"]),
            "composite": a.scores.composite,
            "functional_score": a.functional_value,
            "toxicity": a.scores.toxicity,
            "hemolysis": a.scores.hemolysis,
        })
    return out


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_generator: AnalysisGenerator = TemplateGenerator()


def get_generator() -> AnalysisGenerator:
    return _generator


def register_generator(generator: AnalysisGenerator) -> None:
    """Swap in another implementation, such as a model-backed one."""
    global _generator
    _generator = generator


def llm_configured() -> bool:
    """Whether a model is configured at all, by settings.

    Not the same question as "did this answer come from a model". A model can be configured
    and still fail on one turn; the answer then falls back to the template, and the response's
    `provider` is what says so. This function is used to decide whether to build a model-backed
    generator in the first place.
    """
    from ..config import get_settings
    s = get_settings()
    return bool(s.llm_base_url and s.llm_api_key and s.analysis_provider == "llm")


def build_llm_generator() -> "AnalysisGenerator | None":
    """A model-backed generator, or None when no model is reachable.

    Kept out of module import scope on purpose: the transport is a deployment concern, and the
    analysis module is imported by the tests, by the static exporter and by the service alike.
    A module that reached for an HTTP client at import time would make all three of them depend
    on a model being configured.
    """
    if not llm_configured():
        return None
    try:
        from ..config import get_settings
        from .llm import TIMEOUT_SECONDS, LlmGenerator, chat_completions_endpoint
        import json
        import urllib.request

        s = get_settings()
        endpoint = chat_completions_endpoint(s.llm_base_url or "")

        def call_model(messages: list[dict[str, str]]) -> str | None:
            payload = json.dumps({
                "model": s.llm_model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 700,
            }).encode("utf-8")
            request = urllib.request.Request(
                endpoint,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {s.llm_api_key}",
                },
            )
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                body = json.loads(response.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]

        return LlmGenerator(call_model)
    except Exception as exc:  # noqa: BLE001
        log.warning("could not build the model-backed generator: %s", exc)
        return None


def ensure_generator() -> AnalysisGenerator:
    """Register the model generator when one is configured, and report which is active.

    Idempotent in the sense that a service which already has a model-backed generator is not
    given a second one. With no model configured the check cannot short-circuit — the
    registered generator is the template, whose name is not `llm` — so the settings are read
    once more per call. That is deliberate: the alternative is a flag that would keep the
    service from noticing a model configured after startup, and what it buys back is one
    `lru_cache` hit on a `Settings` object.
    """
    global _generator
    if getattr(_generator, "name", None) == PROVIDER_LLM:
        return _generator
    model_generator = build_llm_generator()
    if model_generator is not None:
        _generator = model_generator
        from ..config import get_settings
        log.info("analysis provider: model-backed (%s)", get_settings().llm_model)
    return _generator


def build_response(c: ConstructDetail) -> tuple[str, list[AnalysisBlock]]:
    g = get_generator()
    return g.name, g.blocks(c)


def _accepts_history(generator: AnalysisGenerator) -> bool:
    """Whether this generator's `answer` takes the `history` keyword.

    Asked of the signature rather than discovered by catching `TypeError`. A `TypeError`
    raised *inside* an answer is a bug in that generator, and a fallback that retried the call
    without the keyword would swallow it and return prose written past the failing line.
    """
    try:
        parameters = inspect.signature(generator.answer).parameters
    except (TypeError, ValueError):  # not inspectable, e.g. a C-level callable
        return False
    return "history" in parameters or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()
    )


def chat(
    c: ConstructDetail,
    question: str,
    history: list[ChatMessage] | None = None,
) -> ChatResponse:
    """Answer one question, and say which generator answered it.

    The fallback lives here rather than inside the model-backed generator because the two
    things that must agree — the text and the label naming its source — are decided together
    at this point and nowhere else. A generator that fails raises `ModelUnavailable`; the
    template's answer is written here, and `provider` moves with it, so a response whose text
    came from the template cannot claim to be a model's.
    """
    g = get_generator()
    turns = [
        {"role": m.role, "content": m.content}
        for m in (history or [])
        if m.role in ("user", "assistant")
    ]

    if _accepts_history(g):
        try:
            content, provider = g.answer(c, question, history=turns), g.name
        except ModelUnavailable as exc:
            log.warning("no model answer for %s (%s); answering from the record", c.id, exc)
            content, provider = TemplateGenerator().answer(c, question), PROVIDER_TEMPLATE
    else:
        # A generator written against the original two-argument protocol. Kept so a
        # third-party generator does not have to be rewritten to keep working.
        content, provider = g.answer(c, question), g.name

    message = ChatMessage(
        id=f"msg_{uuid.uuid4().hex[:12]}",
        role="assistant",
        content=content,
        timestamp=datetime.now(timezone.utc).isoformat(),
        actions=[],
    )
    suggested = getattr(g, "suggested_questions", None)
    return ChatResponse(
        provider=provider,
        construct_id=c.id,
        message=message,
        suggested_questions=suggested(c) if callable(suggested) else [],
        llm_configured=(provider == PROVIDER_LLM),
    )
