/**
 * Joins the service responses into the shapes the pages render.
 *
 * The API keeps resources separate: a route carries `scaffold_ids`, and a scaffold carries
 * `route_ids`, so the relation exists in one direction and cannot disagree with itself. A
 * page that needs the other direction builds it here. That is cheaper than a second endpoint
 * with its own copy of the relation.
 */
import type { MaterialForm, ReferenceData, ScaffoldSummary } from "@/api/types"

export function groupScaffoldsByRoute(
  scaffolds: ScaffoldSummary[],
): Map<string, ScaffoldSummary[]> {
  const byRoute = new Map<string, ScaffoldSummary[]>()
  for (const scaffold of scaffolds) {
    for (const routeId of scaffold.route_ids) {
      const bucket = byRoute.get(routeId)
      if (bucket) bucket.push(scaffold)
      else byRoute.set(routeId, [scaffold])
    }
  }
  return byRoute
}

/** Material-form id to display label, from the reference response rather than a local table. */
export function materialFormLabels(reference: ReferenceData | null): Record<string, string> {
  const labels: Record<string, string> = {}
  for (const option of reference?.material_forms ?? []) labels[option.id] = option.label
  return labels
}

export function formLabel(
  labels: Record<string, string>,
  form: MaterialForm | string,
): string {
  return labels[form] ?? String(form).replace(/-/g, " ")
}

/** Distinct material forms present across a set of scaffolds, in first-seen order. */
export function distinctForms(scaffolds: ScaffoldSummary[]): MaterialForm[] {
  const seen = new Set<MaterialForm>()
  for (const scaffold of scaffolds) {
    for (const form of scaffold.material_forms) seen.add(form)
  }
  return [...seen]
}

/** Highest evidence level present, by the ordinal the labels encode. */
export function highestEvidence(scaffolds: ScaffoldSummary[]): string | null {
  let best: string | null = null
  for (const scaffold of scaffolds) {
    const level = scaffold.max_evidence
    if (!level) continue
    if (best === null || level > best) best = level
  }
  return best
}

export function totalSequenceCount(scaffolds: ScaffoldSummary[]): number {
  return scaffolds.reduce((sum, scaffold) => sum + scaffold.sequence_count, 0)
}

/** 20248885 -> "20.2 M"; 496 -> "496". Used for counts a reader scans rather than reads. */
export function formatCount(value: number): string {
  if (value >= 1_000_000) {
    const millions = value / 1_000_000
    return `${millions.toFixed(millions >= 100 ? 0 : 1)} M`
  }
  if (value >= 10_000) return `${Math.round(value / 1000)} K`
  return value.toLocaleString()
}
