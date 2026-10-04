/**
 * Reading a score against its threshold, and formatting a score for display.
 *
 * Both jobs used to live in a mock module that also carried the thresholds themselves. The
 * thresholds now arrive with the response, so what remains here is only the comparison rule
 * and the presentation. Two conventions are load-bearing:
 *
 *   A missing value is not a failing value. Every score is nullable, and a null renders as
 *   "Not assessed". The previous interface substituted 0 for anything it lacked, which the
 *   tool table then read back as a real score of zero and printed with a FAIL badge —
 *   immunogenicity was shown as a hard failure for 379 of 496 constructs on which the
 *   predictor had never run.
 *
 *   A score that is not assessed has no verdict to show. `judgeScore` returns null for it
 *   rather than reaching for the threshold, so a caller cannot accidentally colour it.
 */
import type { SafetyVerdict, SafetyVerdictKind, ScoreMeta } from "@/api/types"

export type ScoreVerdict = "PASS" | "FAIL" | "WATCH" | null

/** Verdict for one score against the threshold the service applied to it. */
export function judgeScore(meta: ScoreMeta, value: number | null): ScoreVerdict {
  if (value === null) return null
  // A ranking signal has no verdict to give. The anti-inflammatory and anti-melanin scores
  // order candidates; a PASS badge on one would read as a threshold the model never
  // established, which is the reading the pipeline's own metadata forbids.
  if (meta.semantics === "ranking_only") return null
  const threshold = meta.applied_threshold?.value
  if (threshold === undefined || threshold === null) return null

  if (meta.higher_is_better) return value >= threshold ? "PASS" : "WATCH"
  if (value >= threshold) return "FAIL"
  if (value >= threshold * 0.7) return "WATCH"
  return "PASS"
}

export function verdictBadgeVariant(
  verdict: ScoreVerdict,
): "accent" | "destructive" | "warning" | "secondary" {
  if (verdict === "PASS") return "accent"
  if (verdict === "FAIL") return "destructive"
  if (verdict === "WATCH") return "warning"
  return "secondary"
}

export function verdictTextColour(verdict: ScoreVerdict): string {
  if (verdict === "FAIL") return "text-red-600"
  if (verdict === "WATCH") return "text-amber-600"
  return "text-primary-700"
}

/** Bar colour for a score. A score with no verdict — unassessed, or a ranking signal — gets
 *  the neutral track rather than the clearing green. */
export function verdictBarColour(verdict: ScoreVerdict): string {
  if (verdict === "FAIL") return "bg-red-400"
  if (verdict === "WATCH") return "bg-amber-400"
  if (verdict === "PASS") return "bg-accent-500"
  return "bg-gray-300"
}

// ── Formatting ──────────────────────────────────────────────────────────────

/**
 * A score at the given precision, or an em dash when the predictor did not cover this peptide.
 *
 * A measured value that rounds to nothing at that precision is shown with significant digits
 * instead. pLM4CPPs returns values like 2.98e-05, which printed as "0.00" — the same
 * collapsing of two different states that the interface is careful to avoid between an
 * unassessed metric and one that scored zero.
 */
export function formatScore(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—"
  const rounded = value.toFixed(digits)
  if (value !== 0 && Number(rounded) === 0) return value.toPrecision(2)
  return rounded
}

export function formatThreshold(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "no boundary"
  return value.toFixed(digits)
}

/** Width of a score bar, clamped to the track. */
export function barWidth(value: number | null, maximum = 1): string {
  if (value === null || Number.isNaN(value)) return "0%"
  const ratio = maximum === 0 ? 0 : value / maximum
  return `${Math.min(Math.max(ratio, 0), 1) * 100}%`
}

/**
 * How much of a gate's allowance a measurement has used, as a bar width.
 *
 * The bar reads "100% means sitting exactly on the limit", so it has to know which side the
 * limit is on. A plain value-over-threshold ratio gave the MHC-II percent rank a full bar for
 * a value that passes: the rank fails on a *low* value, so 5.28 against a limit of 2.0 is as
 * far from failure as the scale allows and must render as a short bar, not a long one.
 */
export function gateWidth(
  value: number | null,
  threshold: number,
  higherIsBetter: boolean,
): string {
  if (value === null || Number.isNaN(value)) return "0%"
  if (threshold === 0) return "0%"
  if (higherIsBetter) {
    // Below the limit is a failure: the smaller the value, the more of the allowance is gone.
    if (value <= 0) return "100%"
    return `${Math.min(threshold / value, 1) * 100}%`
  }
  return `${Math.min(Math.max(value / threshold, 0), 1) * 100}%`
}

// ── Safety verdict presentation ─────────────────────────────────────────────

export interface VerdictSkin {
  label: string
  badge: "accent" | "destructive" | "warning" | "secondary"
  text: string
  dot: string
}

const VERDICT_SKIN: Record<SafetyVerdictKind, VerdictSkin> = {
  clear: {
    label: "All assessed gates clear",
    badge: "accent",
    text: "text-accent-700",
    dot: "bg-accent-500",
  },
  borderline: {
    label: "Within the threshold band",
    badge: "warning",
    text: "text-amber-700",
    dot: "bg-amber-400",
  },
  vetoed: {
    label: "Vetoed",
    badge: "destructive",
    text: "text-red-700",
    dot: "bg-red-500",
  },
  indeterminate: {
    label: "No gate assessed",
    badge: "secondary",
    text: "text-gray-500",
    dot: "bg-gray-400",
  },
}

export function verdictSkin(verdict: SafetyVerdictKind): VerdictSkin {
  return VERDICT_SKIN[verdict] ?? VERDICT_SKIN.indeterminate
}

/**
 * A key-to-label lookup built from the gates in the response.
 *
 * `vetoed_by` and `unassessed` carry gate keys, which are snake_case field names. Printing
 * them would put `b_cell_epitope` in front of a reader, so every surface that names a gate
 * resolves it through this.
 */
export function gateLabeller(gates: { key: string; label: string }[]): (key: string) => string {
  return (key) => gates.find((gate) => gate.key === key)?.label ?? key
}

/**
 * The gate that eliminated a candidate, named.
 *
 * The previous interface had a `failed_safety` branch that printed toxicity whatever the
 * actual cause, so a haemolysis failure read as a toxicity failure. Naming the gate is the
 * fix; counting them would only have narrowed the error. The labels come from the response,
 * so this function holds no key list of its own.
 */
export function vetoSummary(safety: SafetyVerdict): string {
  const label = gateLabeller(safety.gates)

  if (safety.vetoed_by.length > 0) {
    return `Eliminated by ${joinNames(safety.vetoed_by.map(label))}`
  }
  if (safety.unassessed.length > 0) {
    return `${joinNames(safety.unassessed.map(label))} not assessed`
  }
  return "All assessed gates clear"
}

/** "A", "A and B", "A, B and C" — so a two-item list is not printed with a bare comma. */
export function joinNames(names: string[]): string {
  if (names.length === 0) return ""
  if (names.length === 1) return names[0]
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
}
