/**
 * Presentation mappings.
 *
 * What stays on the client is what the client owns: which icon stands for which name, and
 * how a weight tier is phrased for a reader. The service names an icon in its response
 * (`icon: "bandage"`), and this module resolves that name to a component; it deliberately
 * does not hold any number that also exists in the database.
 */
import {
  Bandage,
  Droplets,
  Shapes,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sun,
  Syringe,
  Waves,
  Zap,
  type LucideIcon,
} from "lucide-react"

import type { ScoreGroup, WeightTier } from "@/api/types"

const ICONS: Record<string, LucideIcon> = {
  // Function directions
  "shield-check": ShieldCheck,
  "shield-alert": ShieldAlert,
  zap: Zap,
  sun: Sun,
  shield: Shield,
  // Application routes
  bandage: Bandage,
  shapes: Shapes,
  syringe: Syringe,
  droplets: Droplets,
  waves: Waves,
}

/** Resolves an icon name from the service, falling back rather than rendering nothing. */
export function iconFor(name: string | null | undefined, fallback: LucideIcon = Shield): LucideIcon {
  if (!name) return fallback
  return ICONS[name] ?? fallback
}

export const SCORE_GROUP_LABEL: Record<ScoreGroup, string> = {
  function: "Function",
  safety: "Safety",
  developability: "Developability",
}

/**
 * The safety group is named without a count of hard gates. BepiPred-3.0 and the MHC-II percent
 * rank sit in this group and are soft signals, and how many hard gates there are is the
 * service's declaration — restating it here is what let the interface and the pipeline
 * disagree. Each entry now carries `is_veto_gate` and says for itself which it is.
 */
export const SCORE_GROUP_HINT: Record<ScoreGroup, string> = {
  function: "Ranks candidates within the direction",
  safety: "Each entry states whether it is a hard gate or a soft signal",
  developability: "Drives ranking under the route's weighting profile",
}

/** The platform's multiplier convention, phrased for a reader. */
export const WEIGHT_TIER_LABEL: Record<WeightTier, string> = {
  high: "Weighted ×1.8",
  medium: "Normal ×1.0",
  low: "Relaxed ×0.4",
}

/** Shared wording for the three direction-availability states. */
export const DIRECTION_STATUS_LABEL: Record<string, string> = {
  ready: "Ready",
  wip: "Work in progress",
  empty: "No data",
}

/**
 * Where a threshold came from, phrased for a reader.
 *
 * The service carries `tool` / `route` / `project` as tokens, which is right for a field and
 * opaque in a sentence. Any surface that shows the origin resolves it here.
 */
export const THRESHOLD_SOURCE_LABEL: Record<string, string> = {
  tool: "the predictor's own cut-off",
  route: "this route's screening profile",
  project: "a platform-wide constant",
}

export function thresholdSourceLabel(source: string | null | undefined): string {
  if (!source) return "an unspecified source"
  return THRESHOLD_SOURCE_LABEL[source] ?? source
}

export const RIGIDITY_ORDER = [
  "Flexible",
  "Mostly Flexible",
  "Balanced",
  "Mostly Rigid",
  "Rigid",
] as const

export function capitalise(value: string): string {
  if (!value) return value
  return value.charAt(0).toUpperCase() + value.slice(1)
}
