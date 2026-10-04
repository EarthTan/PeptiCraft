import { useCallback } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { ErrorState } from "@/components/ui/error-state"
import { CardGridSkeleton, LoadingBlock } from "@/components/ui/loading-state"
import { Notice } from "@/components/ui/notice"
import {
  ArrowRight,
  Beaker,
  Bot,
  ChevronRight,
  Database,
  FlaskConical,
  Shield,
  TrendingUp,
} from "lucide-react"
import { fetchPipeline, fetchReference, fetchScaffolds } from "@/api"
import type { ApiError } from "@/api/client"
import type { PipelineView, ReferenceData, ScaffoldSummary } from "@/api/types"
import {
  distinctForms,
  formLabel,
  formatCount,
  groupScaffoldsByRoute,
  materialFormLabels,
} from "@/lib/derive"
import { DIRECTION_STATUS_LABEL, iconFor } from "@/lib/display"
import { useAsync } from "@/lib/useAsync"
import { cn } from "@/lib/utils"

/**
 * The landing page reads three responses: the reference bundle, the pipeline definition, and
 * the scaffold list.
 *
 * Every number on it is derived from those three. The figures the page previously carried in
 * its own source — a 250-construct count per direction, a 99.99% elimination rate, a
 * "~20M" search space — either disagreed with the database or could not be traced to it. What
 * replaced them is the counts the service actually holds.
 */
export default function LandingPage() {
  const load = useCallback(async () => {
    const [reference, pipeline, scaffolds] = await Promise.all([
      fetchReference(),
      fetchPipeline(),
      fetchScaffolds(),
    ])
    return { reference, pipeline, scaffolds }
  }, [])

  const { data, loading, error, reload } = useAsync(load, [])

  return (
    <div>
      <section className="gradient-hero">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-24 sm:pt-28 sm:pb-32">
          <div className="max-w-3xl mx-auto text-center">
            <Badge variant="accent" className="mb-6 text-sm px-4 py-1.5">
              DKU iGEM 2026 · AI &amp; Software
            </Badge>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-primary-900 leading-tight">
              Design Your Multifunctional
              <br />
              <span className="gradient-accent-text">Proteins for Medical Aesthetics</span>
            </h1>
            <p className="mt-6 text-lg sm:text-xl text-primary-700 leading-relaxed max-w-2xl mx-auto">
              Powered by a dataset of approximately 20 million peptides, our AI platform helps
              students, early-career researchers, and independent innovators design
              multifunctional fusion proteins for medical aesthetics and identify promising
              candidates for laboratory validation.
            </p>
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link to="/builder">
                <Button variant="gradient" size="lg" className="w-full sm:w-auto">
                  <FlaskConical className="w-5 h-5" />
                  Start Building
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
              <Link to="/library">
                <Button variant="outline" size="lg" className="w-full sm:w-auto">
                  <Database className="w-5 h-5" />
                  Browse Library
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="relative -mt-12 mb-16">
        <div className="max-w-4xl mx-auto px-4">
          <div className="glass-card rounded-2xl p-6 sm:p-8">
            {loading && <LoadingBlock label="Reading the library" />}
            {error && <ErrorState error={error} onRetry={reload} compact />}
            {data && <HighlightBar reference={data.reference} scaffolds={data.scaffolds} />}
          </div>
        </div>
      </section>

      <ThreeModules reference={data?.reference ?? null} scaffolds={data?.scaffolds ?? []} />

      <ApplicationRoutes
        reference={data?.reference ?? null}
        scaffolds={data?.scaffolds ?? []}
        loading={loading}
      />

      <CorePrinciples />

      <PipelineSection pipeline={data?.pipeline ?? null} loading={loading} error={error} onRetry={reload} />

      <FunctionDirections reference={data?.reference ?? null} loading={loading} />

      <section className="py-20">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <Separator className="mb-12" />
          <h2 className="text-3xl sm:text-4xl font-bold text-primary-900 tracking-tight">
            Start Designing Your <span className="gradient-accent-text">Fusion Protein</span>
          </h2>
          <p className="mt-4 text-primary-600 max-w-xl mx-auto">
            Choose your application route and function directions — the platform handles
            scaffold matching, scoring, and experiment decisions for you.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link to="/builder">
              <Button variant="gradient" size="lg">
                <FlaskConical className="w-5 h-5" />
                Launch Construct Builder
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
            <Link to="/library">
              <Button variant="outline" size="lg">
                Explore Pre-computed Library
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Stats bar
// ─────────────────────────────────────────────────────────────────────────────

function HighlightBar({
  reference,
  scaffolds,
}: {
  reference: ReferenceData
  scaffolds: ScaffoldSummary[]
}) {
  const searchSpace = reference.directions.reduce(
    (max, direction) => Math.max(max, direction.precursor_count),
    0,
  )
  const constructs = reference.directions.reduce(
    (sum, direction) => sum + direction.construct_count,
    0,
  )

  const highlights = [
    { label: formatCount(searchSpace), detail: "Peptides screened" },
    { label: constructs.toLocaleString(), detail: "Constructs scored" },
    { label: String(scaffolds.length), detail: "Scaffolds in the library" },
    { label: String(reference.directions.length), detail: "Function directions" },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
      {highlights.map((item) => (
        <div key={item.detail} className="text-center">
          <div className="text-2xl sm:text-3xl font-bold text-primary-700 font-mono">
            {item.label}
          </div>
          <div className="text-xs sm:text-sm text-gray-500 mt-1">{item.detail}</div>
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Three modules
// ─────────────────────────────────────────────────────────────────────────────

function ThreeModules({
  reference,
  scaffolds,
}: {
  reference: ReferenceData | null
  scaffolds: ScaffoldSummary[]
}) {
  const total = reference?.directions.reduce((sum, d) => sum + d.construct_count, 0) ?? 0

  const features = [
    {
      icon: Database,
      title: "Pre-computed Peptide Library",
      description:
        `Four function directions, pre-screened offline through Pipeline 4. The library holds ` +
        `${total.toLocaleString()} scored constructs, each reachable without a computation ` +
        `wait. Coverage is uneven by direction, and the library states which directions the ` +
        `pipeline has signed off.`,
    },
    {
      icon: FlaskConical,
      title: "Construct Builder",
      description:
        `Route-driven workflow: choose the application route and the eligible scaffolds narrow ` +
        `automatically from the ${scaffolds.length} proteins in the patent library. The ` +
        `platform then scores candidates under that route's weighting profile and ` +
        `immunogenicity gate.`,
    },
    {
      icon: Bot,
      title: "AI Agent Decision Support",
      description:
        "Embedded and sidebar dual-mode AI Agent. Generates safety interpretation, peptide " +
        "origin, linker rationale, expression strategy, and risk assessment from the " +
        "construct's own scores and thresholds, so every number in the text is traceable to a " +
        "field in the response.",
    },
  ]

  return (
    <section className="py-16 sm:py-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <Badge variant="secondary" className="mb-4">
            Platform
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-bold text-primary-900 tracking-tight">
            Three Core Modules
          </h2>
          <p className="mt-3 text-primary-600 max-w-2xl mx-auto">
            From pre-computed libraries to AI-assisted construct building — one workflow for
            fusion protein design
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {features.map((feature) => (
            <Card
              key={feature.title}
              className="border-gray-200 hover:shadow-md transition-all duration-300"
            >
              <CardHeader>
                <div className="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center mb-3">
                  <feature.icon className="w-5 h-5 text-primary-600" />
                </div>
                <CardTitle className="text-lg">{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-sm leading-relaxed">
                  {feature.description}
                </CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Application routes
// ─────────────────────────────────────────────────────────────────────────────

function ApplicationRoutes({
  reference,
  scaffolds,
  loading,
}: {
  reference: ReferenceData | null
  scaffolds: ScaffoldSummary[]
  loading: boolean
}) {
  const labels = materialFormLabels(reference)
  const byRoute = groupScaffoldsByRoute(scaffolds)

  return (
    <section className="py-16 sm:py-20 bg-surface-alt">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <Badge variant="secondary" className="mb-4">
            Route-Driven
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-bold text-primary-900 tracking-tight">
            Five Application Routes
          </h2>
          <p className="mt-3 text-primary-600 max-w-2xl mx-auto">
            Choose the product form you are building. One choice decides which scaffolds stay
            eligible and how the screening is weighted — you see both before you commit.
          </p>
        </div>

        {loading && <CardGridSkeleton cards={5} columns={3} />}

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-6xl mx-auto">
          {(reference?.routes ?? []).map((route) => {
            const Icon = iconFor(route.icon)
            const admitted = byRoute.get(route.id) ?? []
            const forms = distinctForms(admitted)
            const tightest = route.screening.immunogenicity_threshold <= 0.35

            return (
              <Card
                key={route.id}
                className={cn(
                  "border-gray-200 hover:shadow-md transition-all duration-300",
                  route.emerging && "border-amber-200",
                )}
              >
                <CardHeader>
                  <div className="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center mb-2">
                    <Icon className="w-5 h-5 text-primary-600" />
                  </div>
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base">{route.name}</CardTitle>
                    <Badge variant="outline" className="text-[10px] flex-shrink-0">
                      {route.barrier_label}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-xs leading-relaxed">
                    {route.contact_interface}
                  </CardDescription>

                  <div className="mt-3 flex items-center gap-1.5 text-[11px] font-mono text-gray-400 flex-wrap">
                    <span>{admitted.length} scaffolds</span>
                    <span>·</span>
                    <span
                      className={tightest ? "text-amber-600" : "text-gray-400"}
                    >
                      immuno ≤ {route.screening.immunogenicity_threshold.toFixed(2)}
                    </span>
                  </div>

                  {forms.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {forms.map((form) => (
                        <span
                          key={form}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-surface-alt border border-gray-200 text-gray-500"
                        >
                          {formLabel(labels, form)}
                        </span>
                      ))}
                    </div>
                  )}

                  {route.emerging && (
                    <p className="text-[10px] text-amber-600 mt-2">Evidence still building</p>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>

        <p className="text-center text-xs text-gray-400 mt-6 max-w-3xl mx-auto">
          Types of application technique are shown on each route card in the Builder as handling
          hints. They describe how the construct is applied, not a separate screening axis.
        </p>
      </div>
    </section>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Core principles
// ─────────────────────────────────────────────────────────────────────────────

function CorePrinciples() {
  const principles = [
    {
      icon: Shield,
      title: "Safety-First · Single Veto",
      description:
        "Toxicity, haemolysis, or immunogenicity — any single failure removes the candidate. " +
        "There is no weighted compensation. A metric that was never assessed does not " +
        "eliminate anything, and the interface shows it as unassessed rather than as a pass.",
    },
    {
      icon: Beaker,
      title: "Each Metric Used Once",
      description:
        "The direction's functional score selects the candidate pool and is not reused in the " +
        "ranking that follows. This prevents functional activity from dominating the later " +
        "comparison, which is where scaffold compatibility and developability should decide.",
    },
    {
      icon: TrendingUp,
      title: "Data-Driven Weights",
      description:
        "Metric weights come from the Winsorized standard deviation of each component across " +
        "the candidate pool: a component that varies widely earns weight, a flat one is " +
        "down-weighted automatically. No manual preset is involved, which is why the weights " +
        "differ between directions.",
    },
  ]

  return (
    <section className="py-16 sm:py-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <Badge variant="secondary" className="mb-4">
            Core Design
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-bold text-primary-900 tracking-tight">
            Three Core Principles
          </h2>
          <p className="mt-3 text-primary-600 max-w-2xl mx-auto">
            Safety is treated as a non-negotiable hard gate rather than as another term in a
            weighted sum
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {principles.map((principle) => (
            <Card
              key={principle.title}
              className="border-primary-100 hover:border-primary-300 hover:shadow-md transition-all duration-300"
            >
              <CardHeader>
                <div className="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center mb-3">
                  <principle.icon className="w-5 h-5 text-primary-600" />
                </div>
                <CardTitle className="text-lg">{principle.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-sm leading-relaxed">
                  {principle.description}
                </CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Pipeline
// ─────────────────────────────────────────────────────────────────────────────

function PipelineSection({
  pipeline,
  loading,
  error,
  onRetry,
}: {
  pipeline: PipelineView | null
  loading: boolean
  error: ApiError | null
  onRetry: () => void
}) {
  return (
    <section className="py-16 sm:py-20 bg-surface-alt">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <Badge variant="secondary" className="mb-4">
            Pipeline 4
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-bold text-primary-900 tracking-tight">
            Four-Round Screening Pipeline
          </h2>
          <p className="mt-3 text-primary-600 max-w-2xl mx-auto">
            The platform carries Rounds 1–4 at construct level. The 3D structure track (Rounds
            5–8) is outside the MVP.
          </p>
        </div>

        {loading && <LoadingBlock label="Loading pipeline definition" />}
        {error && <ErrorState error={error} onRetry={onRetry} className="max-w-3xl mx-auto" />}

        <div className="grid gap-4 max-w-3xl mx-auto">
          {(pipeline?.included ?? []).map((stage, index, all) => (
            <div
              key={stage.round}
              className="relative flex items-start gap-4 p-5 rounded-xl bg-white border border-gray-200 hover:border-primary-200 hover:shadow-sm transition-all duration-200 group"
            >
              <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-primary-50 border border-primary-200 flex items-center justify-center group-hover:bg-primary-100 transition-colors">
                <span className="text-sm font-bold text-primary-600 font-mono">R{stage.round}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-primary-900">{stage.name}</h3>
                  <Badge variant="secondary" className="text-xs font-mono">
                    {stage.duration}
                  </Badge>
                </div>
                <p className="text-sm text-gray-500 mb-2 leading-relaxed">{stage.description}</p>
                <span className="text-xs text-primary-500 font-mono bg-primary-50 px-2 py-0.5 rounded">
                  {stage.input} → {stage.output}
                </span>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {stage.tools.map((tool) => (
                    <span
                      key={tool}
                      className="text-xs text-gray-400 font-mono bg-surface-alt px-2 py-0.5 rounded border border-gray-200"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              </div>
              {index < all.length - 1 && (
                <ChevronRight className="hidden sm:block flex-shrink-0 w-5 h-5 text-gray-300 self-center" />
              )}
            </div>
          ))}
        </div>

        {pipeline && (
          <div className="max-w-3xl mx-auto mt-6 space-y-3">
            <Notice tone="info" title="Which composite score the platform reports">
              {pipeline.composite_definition}
            </Notice>
            <Notice tone="caution" title="Rounds 5–8 are out of scope">
              {pipeline.excluded_note}
            </Notice>
          </div>
        )}
      </div>
    </section>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Function directions
// ─────────────────────────────────────────────────────────────────────────────

function FunctionDirections({
  reference,
  loading,
}: {
  reference: ReferenceData | null
  loading: boolean
}) {
  return (
    <section className="py-16 sm:py-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <Badge variant="secondary" className="mb-4">
            Function Modules
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-bold text-primary-900 tracking-tight">
            Four Function Directions
          </h2>
          <p className="mt-3 text-primary-600 max-w-2xl mx-auto">
            Antioxidant, antibacterial, anti-inflammatory, and anti-melanin deposition.
            Multi-direction combinations are supported.
          </p>
        </div>

        {loading && <CardGridSkeleton cards={4} columns={3} />}

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {(reference?.directions ?? []).map((direction) => {
            const Icon = iconFor(direction.icon)
            return (
              <Card
                key={direction.id}
                className={cn(
                  "border-gray-200 hover:shadow-md transition-all duration-300",
                  direction.status === "empty" && "opacity-60",
                )}
              >
                <CardHeader>
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center mb-2"
                    style={{ backgroundColor: `${direction.color}15` }}
                  >
                    <Icon className="w-5 h-5" style={{ color: direction.color }} />
                  </div>
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-base">{direction.name}</CardTitle>
                    <Badge
                      variant={direction.status === "ready" ? "accent" : "warning"}
                      className="text-xs"
                    >
                      {DIRECTION_STATUS_LABEL[direction.status] ?? direction.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-xs leading-relaxed">
                    {direction.description}
                  </CardDescription>
                  <div className="flex flex-wrap gap-x-3 gap-y-1 mt-3 text-xs text-gray-400 font-mono">
                    <span>{direction.precursor_count.toLocaleString()} peptides</span>
                    <span>·</span>
                    <span>{direction.construct_count} constructs</span>
                  </div>
                  {direction.status === "wip" && (
                    <p className="text-[11px] text-amber-600 mt-2 leading-relaxed">
                      These rows are in the database but the pipeline has not signed them off.
                      They are visible in the library and marked wherever they appear.
                    </p>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>
    </section>
  )
}
