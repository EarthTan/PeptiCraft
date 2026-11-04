/**
 * Explanations for the concepts the interface introduces.
 *
 * These are the things a reader outside the project cannot infer from the number printed
 * beside them: a score that folds several predictors into one, a verdict with four grades, a
 * badge that says a direction is not finished, and a gate whose direction runs against the
 * others. The wording sits next to the term rather than in a glossary page, because the
 * question is asked where the term appears.
 *
 * What each *predictor* measures is not written here. The service sends that with every
 * score, in its own `measures` text, and a second copy of it here would be a copy that can
 * drift out of date without anybody noticing.
 */
import type { SafetyVerdictKind } from "@/api/types"

export type GlossaryKey =
  | "composite"
  | "developability"
  | "gates_clear"
  | "threshold_band"
  | "vetoed"
  | "no_gate_assessed"
  | "immunogenicity_gate"
  | "route_profile"
  | "ranking_only"
  | "wip"
  | "pipeline_status"
  | "route_gate"
  | "soft_signal"
  | "veto_gate"
  | "multi_function"
  | "control_arm"
  | "screening_thresholds"

export const GLOSSARY: Record<GlossaryKey, string> = {
  composite:
    "One number that folds the developability signals - penetration, solubility and thermal " +
    "stability - into a single score, weighted by the application route being viewed. It is " +
    "normalised within each function direction, so it ranks candidates inside a direction and " +
    "not across directions. It is an exploratory ranking, not a probability of activity, " +
    "safety or experimental success.",

  developability:
    "The composite under the selected application route: how well the peptide is expected to " +
    "reach and stay in its target tissue, given that route's weighting of penetration, " +
    "solubility and thermal stability.",

  gates_clear:
    "Every safety gate that could be evaluated was passed. Gates the predictors did not cover " +
    "are not counted here - an unassessed gate does not eliminate a candidate.",

  threshold_band:
    "The construct passed, but sits within 10% of a safety gate's limit. A gate inside the " +
    "band is reported as borderline rather than clear.",

  vetoed:
    "At least one veto gate failed, so the construct is eliminated from the candidate set. " +
    "The gate that failed is named underneath.",

  no_gate_assessed:
    "No veto gate could be evaluated for this construct, so it carries no safety verdict yet. " +
    "This is not a pass.",

  immunogenicity_gate:
    "The predicted MHC-I presentation score must be at or below this ceiling; a higher score " +
    "means stronger predicted binding and therefore greater immunogenic risk. Each " +
    "application route sets its own ceiling - 0.35 where the construct contacts tissue fluid " +
    "directly, 0.50 for intact or occluded skin, 0.60 for hair, where it never reaches " +
    "immune tissue. MHC-II binding is reported separately as a percent rank, where a lower " +
    "rank means a stronger binder.",

  route_profile:
    "The application route sets both the immunogenicity ceiling and the weighting of " +
    "penetration, solubility and thermal stability. The same construct scores differently " +
    "under another route.",

  ranking_only:
    "This score orders candidates; it does not measure activity. The predictor behind it " +
    "separates peptides that look functional from random fragments, so the number is a rank " +
    "position rather than a probability.",

  wip:
    "Work in progress. These rows exist in the database, but the pipeline has not signed them " +
    "off - the direction is still being validated. WIP does not mean the data is missing.",

  pipeline_status:
    "The pipeline's own state for this row. Signed off means it cleared every gate, the two " +
    "eliminated states mean it was filtered out, and not signed off means the pipeline has not " +
    "validated the row yet.",

  route_gate:
    "The limit comes from the application route's screening profile rather than from the " +
    "predictor itself. Choosing another route changes the limit.",

  soft_signal:
    "A reported measurement that is not a veto gate. It is shown for context and does not " +
    "eliminate a candidate.",

  veto_gate:
    "A failure on this gate eliminates the candidate from the set. The three gates that can " +
    "eliminate are toxicity, haemolysis and immunogenicity.",

  multi_function:
    "More than one function can be held at once. The rows are then grouped by function and " +
    "each group is ranked on its own, because the composite is normalised inside each " +
    "function's own candidate pool. Two rows from different functions cannot be compared by " +
    "their composite, and the # badge is each row's rank inside its own function.",

  control_arm:
    "A negative control. These rows carry real scores, but the pipeline wrote them to give a " +
    "comparison baseline rather than to be candidates, so they are not part of the screened " +
    "set. The Builder ranks the candidate arm only.",

  screening_thresholds:
    "Limits applied to the candidates before they are ranked. They can only remove " +
    "candidates: the peptide library holds twenty million sequences and the candidates are " +
    "the ones the pipeline has already screened, so no threshold here brings a new peptide in.",
}

/** The explanation that belongs to each safety verdict. */
export const VERDICT_GLOSSARY: Record<SafetyVerdictKind, GlossaryKey> = {
  clear: "gates_clear",
  borderline: "threshold_band",
  vetoed: "vetoed",
  indeterminate: "no_gate_assessed",
}

/**
 * What each direction's activity score measures, keyed by the predictor's own key.
 *
 * The four directions score their peptides with four different predictors, so the number
 * beside the label means a different thing in each of them. The keys are the pipeline's, and
 * they do not share a spelling convention - `imfp_lg_AIP` is capitalised where the others are
 * not - so the lookup is by that key rather than by direction.
 */
export const FUNCTIONAL_SCORE_NOTES: Record<string, string> = {
  "anoxpepred-frs":
    "The antioxidant direction's activity score: the probability that the peptide scavenges " +
    "free radicals, from the free-radical-scavenging head of AnOxPePred. The predictor emits " +
    "a separate chelating head, which is not this number.",

  "amp-esm":
    "The antibacterial direction's activity score: AMPlify's probability that the sequence is " +
    "an antimicrobial peptide.",

  "imfp_lg_AIP":
    "The anti-inflammatory direction's activity score: the anti-inflammatory channel of " +
    "iMFP-LG. It orders candidates and is not a probability of anti-inflammatory activity.",

  tipred:
    "The anti-melanin direction's activity score: TIPred's output. It orders candidates and " +
    "is not a probability of melanogenesis inhibition.",
}
