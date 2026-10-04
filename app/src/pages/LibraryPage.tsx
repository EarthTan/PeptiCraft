import { useCallback, useState, type ReactNode } from "react"
import { Link } from "react-router-dom"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ErrorState } from "@/components/ui/error-state"
import { CardGridSkeleton, ListSkeleton } from "@/components/ui/loading-state"
import { Notice } from "@/components/ui/notice"
import { Skeleton } from "@/components/ui/skeleton"
import {
  AnalysisBlocks,
  SafetyGateList,
  ToolScoreGrid,
} from "@/components/construct-panels"
import { ArrowUpRight, ChevronDown, Dna, Eye, FlaskConical, Layers, Link2 } from "lucide-react"
import {
  fetchConstruct,
  fetchConstructs,
  fetchLinkers,
  fetchReference,
  fetchScaffolds,
} from "@/api"
import type {
  ConstructSummary,
  FunctionDirection,
  LinkerView,
  ReferenceData,
  ScaffoldSummary,
} from "@/api/types"
import { distinctForms, formLabel, materialFormLabels } from "@/lib/derive"
import { iconFor, RIGIDITY_ORDER } from "@/lib/display"
import { formatScore, verdictSkin } from "@/lib/score"
import { useAsync } from "@/lib/useAsync"
import { cn } from "@/lib/utils"

/**
 * The library browser.
 *
 * Three tabs, one per resource. The peptides tab is the one that changed shape: a construct
 * row is scored under an application route's weighting profile and against that route's
 * immunogenicity gate, so the route is a visible control here rather than an implicit default.
 * Without it the page would be showing a composite and a threshold that no reader could name.
 */

const DEFAULT_TAB = "peptides" as const

export default function LibraryPage() {
  const [mainTab, setMainTab] = useState<string>(DEFAULT_TAB)

  const load = useCallback(async () => {
    const [reference, scaffolds, linkers, firstPage] = await Promise.all([
      fetchReference(),
      fetchScaffolds(),
      fetchLinkers(),
      fetchConstructs({ limit: 1 }),
    ])
    return { reference, scaffolds, linkers, constructTotal: firstPage.total }
  }, [])

  const { data, loading, error, reload } = useAsync(load, [])

  const tabs = [
    { id: "peptides", label: "Peptides", icon: Dna, count: data?.constructTotal ?? null },
    { id: "scaffold", label: "Scaffold", icon: Layers, count: data?.scaffolds.length ?? null },
    { id: "linker", label: "Linker", icon: Link2, count: data?.linkers.length ?? null },
  ]

  return (
    <div className="min-h-[calc(100vh-8rem)]">
      <section className="bg-surface-alt border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <Badge variant="accent" className="mb-3">
                Pre-computed
              </Badge>
              <h1 className="text-2xl sm:text-3xl font-bold text-primary-900">Library</h1>
              <p className="text-sm text-gray-500 mt-1">
                Peptides, scaffolds and linkers — every entry read from the project database
              </p>
            </div>
            <Link to="/builder">
              <Button variant="gradient" size="sm">
                <FlaskConical className="w-4 h-4" />
                New Build
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="border-b border-gray-200 bg-white sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex gap-1 overflow-x-auto">
            {tabs.map((tab) => {
              const Icon = tab.icon
              const isActive = mainTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setMainTab(tab.id)}
                  className={cn(
                    "flex items-center gap-2.5 px-5 py-3.5 border-b-2 transition-all duration-200 whitespace-nowrap cursor-pointer",
                    isActive
                      ? "border-primary-500 text-primary-700"
                      : "border-transparent text-gray-500 hover:text-primary-600 hover:border-gray-300",
                  )}
                >
                  <Icon className={cn("w-4 h-4", isActive ? "text-primary-600" : "text-gray-400")} />
                  <span className="font-semibold text-sm">{tab.label}</span>
                  {tab.count === null ? (
                    <Skeleton className="h-5 w-8 rounded-full" />
                  ) : (
                    <Badge variant={isActive ? "accent" : "secondary"} className="text-xs">
                      {tab.count}
                    </Badge>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      </section>

      {error && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <ErrorState error={error} onRetry={reload} />
        </section>
      )}

      {!error && mainTab === "peptides" && (
        <PeptidesPanel
          reference={data?.reference ?? null}
          loading={loading}
        />
      )}
      {!error && mainTab === "scaffold" && (
        <ScaffoldPanel
          reference={data?.reference ?? null}
          scaffolds={data?.scaffolds ?? []}
          loading={loading}
        />
      )}
      {!error && mainTab === "linker" && (
        <LinkerPanel linkers={data?.linkers ?? []} loading={loading} />
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Peptides
// ─────────────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 25

function PeptidesPanel({
  reference,
  loading,
}: {
  reference: ReferenceData | null
  loading: boolean
}) {
  const [direction, setDirection] = useState<string>("all")
  const [routeId, setRouteId] = useState<string | null>(null)
  const [limit, setLimit] = useState(PAGE_SIZE)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const routes = reference?.routes ?? []
  const effectiveRoute = routeId ?? routes[0]?.id ?? null
  const effectiveRouteName =
    routes.find((route) => route.id === effectiveRoute)?.name ?? "the default route"

  const load = useCallback(async () => {
    if (!effectiveRoute) return null
    return fetchConstructs({
      direction: direction === "all" ? null : direction,
      route_id: effectiveRoute,
      limit,
      offset: 0,
    })
  }, [direction, effectiveRoute, limit])

  const { data, loading: rowsLoading, error, reload, refreshing } = useAsync(load, [
    direction,
    effectiveRoute,
    limit,
  ])

  const directions = reference?.directions ?? []
  const rows = data?.items ?? []
  const total = data?.total ?? 0

  const selectDirection = (id: string) => {
    setDirection(id)
    setLimit(PAGE_SIZE)
    setExpandedId(null)
  }

  if (loading || !reference) {
    return (
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <ListSkeleton rows={5} />
      </section>
    )
  }

  return (
    <>
      <section className="border-b border-gray-200 bg-surface-alt/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-400 mr-1">Function:</span>
            <FilterChip
              active={direction === "all"}
              onClick={() => selectDirection("all")}
              label="All"
              count={directions.reduce((sum, item) => sum + item.construct_count, 0)}
            />
            {directions.map((item) => (
              <DirectionChip
                key={item.id}
                direction={item}
                active={direction === item.id}
                onClick={() => selectDirection(item.id)}
              />
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-400 mr-1">Screened under:</span>
            {routes.map((route) => (
              <button
                key={route.id}
                onClick={() => {
                  setRouteId(route.id)
                  setLimit(PAGE_SIZE)
                }}
                className={cn(
                  "px-3 py-1.5 rounded-lg border text-xs font-medium transition-all duration-200 cursor-pointer",
                  effectiveRoute === route.id
                    ? "border-primary-400 bg-primary-50 text-primary-800 shadow-sm"
                    : "border-gray-200 bg-white text-gray-600 hover:border-primary-200",
                )}
                title={route.screening.threshold_note}
              >
                {route.name}
                <span className="ml-1.5 font-mono text-[11px] text-gray-400">
                  ≤{route.screening.immunogenicity_threshold.toFixed(2)}
                </span>
              </button>
            ))}
          </div>

          <p className="text-xs text-gray-400">
            Composite and safety verdict are computed under the <strong>{effectiveRouteName}</strong>{" "}
            profile: immunogenicity gate{" "}
            {routes
              .find((route) => route.id === effectiveRoute)
              ?.screening.immunogenicity_threshold.toFixed(2) ?? "—"}
            , and that route's weighting for penetration, solubility and thermal stability. The
            same construct scores differently under another route.
          </p>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {rowsLoading && <ListSkeleton rows={5} />}
        {error && <ErrorState error={error} onRetry={reload} />}

        {!rowsLoading && !error && (
          <>
            <p className="text-xs text-gray-400 mb-3">
              {total.toLocaleString()} construct{total === 1 ? "" : "s"} match · showing{" "}
              {rows.length}
              {refreshing && <span className="ml-2 text-primary-400">updating…</span>}
            </p>

            <div className="space-y-3">
              {rows.map((construct) => (
                <ConstructRow
                  key={construct.id}
                  construct={construct}
                  routeId={effectiveRoute}
                  expanded={expandedId === construct.id}
                  onToggle={() =>
                    setExpandedId(expandedId === construct.id ? null : construct.id)
                  }
                />
              ))}
            </div>

            {rows.length === 0 && (
              <div className="text-center py-16">
                <Dna className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500">No constructs in this function category</p>
              </div>
            )}

            {rows.length < total && (
              <div className="text-center mt-6">
                <Button
                  variant="outline"
                  onClick={() => setLimit((current) => current + PAGE_SIZE)}
                >
                  Show more ({total - rows.length} remaining)
                </Button>
              </div>
            )}
          </>
        )}
      </section>
    </>
  )
}

function DirectionChip({
  direction,
  active,
  onClick,
}: {
  direction: FunctionDirection
  active: boolean
  onClick: () => void
}) {
  const Icon = iconFor(direction.icon)
  const unavailable = direction.status === "empty"

  return (
    <button
      onClick={onClick}
      disabled={unavailable}
      className={cn(
        "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-all duration-200",
        unavailable
          ? "border-dashed border-gray-200 text-gray-400 cursor-not-allowed"
          : active
            ? "border-primary-400 bg-primary-50 text-primary-800 shadow-sm cursor-pointer"
            : "border-gray-200 bg-white text-gray-600 hover:border-primary-200 cursor-pointer",
      )}
      title={
        direction.status === "wip"
          ? "These rows exist in the database but the pipeline has not signed them off."
          : direction.description
      }
    >
      <Icon className="w-3 h-3" style={{ color: unavailable ? undefined : direction.color }} />
      <span className="font-medium">{direction.name}</span>
      <span className={cn("font-mono", unavailable ? "text-gray-300" : "text-gray-400")}>
        {direction.construct_count}
      </span>
      {direction.status === "wip" && (
        <span className="text-[10px] text-amber-600 font-medium">WIP</span>
      )}
    </button>
  )
}

function ConstructRow({
  construct,
  routeId,
  expanded,
  onToggle,
}: {
  construct: ConstructSummary
  routeId: string | null
  expanded: boolean
  onToggle: () => void
}) {
  const skin = verdictSkin(construct.safety_verdict ?? "indeterminate")
  const isCandidate = construct.status === "passed"

  return (
    <Card
      className={cn(
        "border-gray-200 hover:border-primary-200 hover:shadow-sm transition-all duration-200 overflow-hidden",
        !isCandidate && "opacity-80",
        expanded && "border-primary-300 shadow-md",
      )}
    >
      <div onClick={onToggle} className="p-4 sm:p-5 cursor-pointer select-none">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <ChevronDown
                className={cn(
                  "w-4 h-4 text-gray-400 transition-transform duration-200",
                  expanded && "rotate-180",
                )}
              />
              <span className="font-mono text-sm font-semibold text-primary-900">
                {construct.name}
              </span>
              {construct.rank !== null && (
                <Badge variant="outline" className="text-xs">
                  #{construct.rank}
                </Badge>
              )}
              <Badge variant="secondary" className="text-[10px]">
                {construct.direction_label}
              </Badge>
              {!isCandidate && (
                <Badge variant="warning" className="text-[10px]">
                  Pipeline status {construct.status}
                </Badge>
              )}
            </div>

            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 ml-6">
              <span className="font-mono text-primary-600 break-all">
                {construct.peptide_sequence}
              </span>
              <span className="text-gray-400">{construct.peptide_length} aa</span>
            </div>

            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-gray-400 ml-6 mt-1">
              <span>
                Scaffold:{" "}
                {construct.backbone_binding === "placeholder" ? (
                  <span className="text-amber-600">unassigned (placeholder binding)</span>
                ) : (
                  <span className="text-gray-600">
                    {construct.backbone_name ?? "—"}
                    <span className="ml-1 text-gray-400">
                      ({construct.backbone_binding})
                    </span>
                  </span>
                )}
              </span>
              <span>·</span>
              <span>Linker: {construct.linker_name ?? "—"}</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 sm:gap-4">
            <div className={cn("flex items-center gap-1.5 text-xs font-medium", skin.text)}>
              <span className={cn("w-1.5 h-1.5 rounded-full", skin.dot)} />
              {skin.label}
            </div>

            <ScoreCell label="Composite" value={construct.composite} />
            <ScoreCell
              label={construct.functional_score_label}
              value={construct.functional_score}
              rankingOnly={construct.semantics === "ranking_only"}
              small
            />

            <div onClick={(event) => event.stopPropagation()}>
              <Link to={`/results/${construct.id}${routeId ? `?route_id=${routeId}` : ""}`}>
                <Button variant="ghost" size="icon" className="text-gray-400 hover:text-primary-600">
                  <Eye className="w-4 h-4" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {expanded && <ConstructExpanded constructId={construct.id} routeId={routeId} />}
    </Card>
  )
}

function ScoreCell({
  label,
  value,
  small,
  rankingOnly = false,
}: {
  label: string
  value: number | null
  small?: boolean
  /** The value orders candidates and is not a probability, so it is not colour-banded as one. */
  rankingOnly?: boolean
}) {
  return (
    <div className="text-center min-w-[56px]">
      <div className="text-[10px] text-gray-400 truncate max-w-[80px]" title={label}>
        {label}
      </div>
      <div
        className={cn(
          "font-mono font-bold rounded px-1.5 py-0.5",
          small ? "text-xs" : "text-sm",
          value === null
            ? "text-gray-300 bg-surface-alt"
            : rankingOnly
              ? "text-primary-700 bg-surface-alt"
              : value >= 0.8
                ? "text-accent-600 bg-accent-50"
                : value >= 0.6
                  ? "text-primary-600 bg-primary-50"
                  : "text-amber-600 bg-amber-50",
        )}
      >
        {formatScore(value)}
      </div>
      {rankingOnly && (
        <div className="text-[9px] text-gray-400 mt-0.5">ranking only</div>
      )}
    </div>
  )
}

/**
 * Lazy detail for one expanded row.
 *
 * The list response carries enough to render a row but not the gate values or the per-tool
 * metadata, so expanding fetches the detail. That keeps the first paint at one request
 * regardless of how many rows the page shows.
 */
function ConstructExpanded({
  constructId,
  routeId,
}: {
  constructId: string
  routeId: string | null
}) {
  const detail = useAsync(
    () => fetchConstruct(constructId, { route_id: routeId }),
    [constructId, routeId],
  )

  return (
    <div className="border-t border-gray-200 bg-surface-alt/40 p-4 sm:p-5 space-y-5">
      {detail.loading && <Skeleton className="h-40 w-full" />}
      {detail.error && <ErrorState error={detail.error} onRetry={detail.reload} compact />}
      {detail.data && (
        <>
          <SafetyGateList safety={detail.data.safety} />
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Tool-by-tool scores
            </p>
            <ToolScoreGrid scores={detail.data.scores} scoreMeta={detail.data.score_meta} />
          </div>
          {detail.data.backbone_binding === "placeholder" && (
            <Notice tone="caution" title="Scaffold binding is a placeholder">
              No fused sequence is shown for this construct. The stored record points at a
              placeholder scaffold row, so the backbone segment has no sequence and the two
              remaining parts cannot be presented as an assembled construct.
              <Link
                to={`/results/${constructId}${routeId ? `?route_id=${routeId}` : ""}`}
                className="ml-1 underline"
              >
                Open the construct page
              </Link>{" "}
              to preview an assembly against a real scaffold.
            </Notice>
          )}
          <AnalysisBlocks constructId={constructId} routeId={routeId} />
        </>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Scaffolds
// ─────────────────────────────────────────────────────────────────────────────

function ScaffoldPanel({
  reference,
  scaffolds,
  loading,
}: {
  reference: ReferenceData | null
  scaffolds: ScaffoldSummary[]
  loading: boolean
}) {
  const [category, setCategory] = useState<string>("all")

  const labels = materialFormLabels(reference)
  const filtered =
    category === "all" ? scaffolds : scaffolds.filter((item) => item.category === category)

  if (loading || !reference) {
    return (
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <CardGridSkeleton cards={6} />
      </section>
    )
  }

  return (
    <>
      <section className="border-b border-gray-200 bg-surface-alt/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-400 mr-1">Category:</span>
            <FilterChip
              active={category === "all"}
              onClick={() => setCategory("all")}
              label="All"
              count={scaffolds.length}
            />
            {reference.categories.map((group) => (
              <FilterChip
                key={group.id}
                active={category === group.id}
                onClick={() => setCategory(group.id)}
                label={group.label}
                count={group.scaffold_ids.length}
              />
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {filtered.length} scaffold{filtered.length === 1 ? "" : "s"} — open any card for
            patent variants, applicant and the experiments behind its evidence label.
          </p>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid md:grid-cols-2 gap-4">
          {filtered.map((scaffold) => {
            const forms = distinctForms([scaffold])
            const routes = scaffold.route_ids
            return (
              <Link key={scaffold.id} to={`/library/scaffold/${scaffold.id}`} className="block group">
                <Card className="border-gray-200 hover:border-primary-300 hover:shadow-md transition-all duration-200 p-5 h-full">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold text-primary-900 group-hover:text-primary-700">
                          {scaffold.short_name}
                        </h3>
                        {scaffold.length !== null && (
                          <Badge variant="secondary" className="text-xs">
                            {scaffold.length} aa
                          </Badge>
                        )}
                        {scaffold.max_evidence && (
                          <Badge variant="accent" className="text-xs">
                            {scaffold.max_evidence}
                          </Badge>
                        )}
                        {!scaffold.has_sequence && (
                          <Badge variant="warning" className="text-xs">
                            no sequence
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">{scaffold.name}</p>
                    </div>
                    <ArrowUpRight className="w-4 h-4 text-gray-300 group-hover:text-primary-500 transition-colors flex-shrink-0" />
                  </div>

                  {scaffold.species && (
                    <p className="text-xs text-gray-500 italic leading-relaxed">
                      {scaffold.species}
                    </p>
                  )}

                  <dl className="mt-3 pt-3 border-t border-gray-100 space-y-1 text-[11px]">
                    <div className="flex gap-2">
                      <dt className="text-gray-400 flex-shrink-0 w-16">Applicant</dt>
                      <dd className="text-gray-600">{scaffold.applicant}</dd>
                    </div>
                    {scaffold.patent && (
                      <div className="flex gap-2">
                        <dt className="text-gray-400 flex-shrink-0 w-16">Patent</dt>
                        <dd className="text-gray-600 line-clamp-1">{scaffold.patent}</dd>
                      </div>
                    )}
                    <div className="flex gap-2">
                      <dt className="text-gray-400 flex-shrink-0 w-16">Variants</dt>
                      <dd className="text-gray-600 font-mono">{scaffold.sequence_count}</dd>
                    </div>
                  </dl>

                  {forms.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2.5">
                      {forms.map((form) => (
                        <Badge key={form} variant="outline" className="text-[10px]">
                          {formLabel(labels, form)}
                        </Badge>
                      ))}
                    </div>
                  )}

                  {routes.length > 0 && (
                    <p className="text-[10px] text-gray-400 mt-2">
                      Admitted by {routes.length} application route
                      {routes.length > 1 ? "s" : ""}
                    </p>
                  )}
                </Card>
              </Link>
            )
          })}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-16">
            <Layers className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No scaffolds in this category</p>
          </div>
        )}
      </section>
    </>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Linkers
// ─────────────────────────────────────────────────────────────────────────────

function LinkerPanel({ linkers, loading }: { linkers: LinkerView[]; loading: boolean }) {
  const [rigidity, setRigidity] = useState<string>("all")

  const counts = RIGIDITY_ORDER.map((band) => ({
    id: band,
    count: linkers.filter((linker) => linker.rigidity === band).length,
  })).filter((entry) => entry.count > 0)

  const filtered = linkers.filter((linker) => rigidity === "all" || linker.rigidity === rigidity)

  if (loading) {
    return (
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <CardGridSkeleton cards={8} columns={3} />
      </section>
    )
  }

  return (
    <>
      <section className="border-b border-gray-200 bg-surface-alt/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-400 mr-1">Rigidity:</span>
            <FilterChip
              active={rigidity === "all"}
              onClick={() => setRigidity("all")}
              label="All"
              count={linkers.length}
            />
            {counts.map((entry) => (
              <FilterChip
                key={entry.id}
                active={rigidity === entry.id}
                onClick={() => setRigidity(entry.id)}
                label={entry.id}
                count={entry.count}
              />
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {linkers.length} linker{linkers.length === 1 ? "" : "s"} from the curated library.
            Each entry is a literature-backed sequence rather than a combinatorial
            concatenation.
          </p>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {filtered.map((linker) => (
            <Card
              key={linker.id}
              className="border-gray-200 hover:border-primary-200 hover:shadow-sm transition-all duration-200 p-5"
            >
              <div className="flex items-center justify-between mb-3 gap-2">
                <span className="font-mono font-bold text-sm text-primary-900">{linker.name}</span>
                <Badge variant="secondary" className="text-[10px] flex-shrink-0">
                  {linker.rigidity}
                </Badge>
              </div>

              <div className="rounded-lg bg-gradient-to-br from-primary-50/60 via-white to-accent-50/40 border border-primary-100 px-3 py-4 mb-3">
                <p className="font-mono text-center text-[15px] text-primary-700 break-all leading-relaxed font-semibold tracking-wide">
                  {linker.sequence}
                </p>
              </div>

              {linker.description && (
                <p className="text-[11px] text-gray-500 leading-relaxed mb-3">
                  {linker.description}
                </p>
              )}

              <div className="flex items-center justify-between pt-3 mt-2 border-t border-gray-100 text-[11px] text-gray-400">
                <span>{linker.length} aa</span>
                {linker.reference && (
                  <span className="line-clamp-1 text-right max-w-[60%]">
                    {linker.reference.split(",")[0]}
                  </span>
                )}
              </div>
            </Card>
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-16">
            <Link2 className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No linkers match this filter</p>
          </div>
        )}
      </section>
    </>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared
// ─────────────────────────────────────────────────────────────────────────────

function FilterChip({
  active,
  onClick,
  disabled,
  label,
  count,
  icon,
}: {
  active: boolean
  onClick: () => void
  disabled?: boolean
  label: string
  count: number
  icon?: ReactNode
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-all duration-200",
        disabled
          ? "border-dashed border-gray-200 text-gray-400 cursor-not-allowed bg-transparent"
          : active
            ? "border-primary-400 bg-primary-50 text-primary-800 shadow-sm cursor-pointer"
            : "border-gray-200 bg-white text-gray-600 hover:border-primary-200 cursor-pointer",
      )}
    >
      {icon}
      <span className="font-medium">{label}</span>
      <span className={cn("font-mono", disabled ? "text-gray-300" : "text-gray-400")}>{count}</span>
    </button>
  )
}
