import { sequenceColor, sequenceWeight } from "@/lib/sequence-colors"
import { BuilderJourney } from "@/components/builder-journey"
import { EvidenceLegend } from "@/components/evidence-badge"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { CSSProperties, ReactNode } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ErrorState } from "@/components/ui/error-state"
import { CardGridSkeleton, ListSkeleton } from "@/components/ui/loading-state"
import { CollapsibleNotice, Notice } from "@/components/ui/notice"
import { InfoTip } from "@/components/ui/tooltip"
import { BuildNameDialog } from "@/components/build-history"
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Eye,
  FlaskConical,
  History,
  Layers,
  Ruler,
  Shield,
  ShieldAlert,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { fetchBuild, fetchLinkers, fetchReference, fetchScaffolds } from "@/api"
import type {
  BuildCounts,
  DeliveryRoute,
  FunctionDirection,
  LinkerView,
  MaterialForm,
  ScaffoldSummary,
  ThresholdReference,
} from "@/api/types"
import { listBuildRecords, recordBuild, renameSession, type BuildRecord } from "@/lib/buildRecords"
import { openHistoryPanel } from "@/lib/historyPanel"
import { distinctForms, formLabel, groupScaffoldsByRoute, materialFormLabels } from "@/lib/derive"
import {
  DIRECTION_STATUS_LABEL,
  iconFor,
  pipelineStatusLabel,
  WEIGHT_TIER_LABEL,
} from "@/lib/display"
import { GLOSSARY, VERDICT_GLOSSARY } from "@/lib/glossary"
import { formatScore, verdictSkin } from "@/lib/score"
import { useAsync } from "@/lib/useAsync"
import { cn } from "@/lib/utils"

/**
 * The construct builder.
 *
 * Five steps, and the last three are the real ones. The application route sets the screening
 * profile every candidate is scored under, and the scaffold and the linker are what each
 * candidate is assembled from: step 5 is not a filtered list of stored rows but a build, with
 * the fused sequence of every candidate as its output.
 *
 * Neither assembly target narrows the candidate list - a scaffold and a linker are assembly
 * targets, not filters - and it is worth being exact about what that means now that the build
 * is real. The *peptides* that come back do not change when either one changes. The *sequences
 * they are built into* do, and so does the fused length on every card. That is the difference
 * between this page and a query over stored constructs.
 *
 * No stored construct carries a real scaffold binding, so the assembly is reported as
 * `inferred`: a faithful concatenation of a real scaffold, a real linker and a real peptide,
 * whose pairing came from this page rather than from the pipeline. The linker is reported
 * separately, because a stored construct does record one - the sample table's first entry,
 * which the assembly script attached rather than chose - so naming one here is the first
 * actual decision made about it.
 */

const STEP_LABELS = ["Route", "Function", "Scaffold", "Linker", "Results"] as const
const STEP_COUNT = STEP_LABELS.length

type Step = 1 | 2 | 3 | 4 | 5

/** How many ranked candidates step 5 asks for. The whole candidate set is ranked before the
 *  page is sliced, so this bounds the response and not the ranking. */
const RESULT_LIMIT = 100

/**
 * The build in progress, kept for this tab.
 *
 * A reload is not a new build, and neither is stepping away to look at one of its constructs,
 * so the name and the place in the five steps survive both. What does not survive is a new
 * build: "Start Building" carries a `new` marker in the address, and honouring it is what
 * makes every start begin with its own name instead of the last one.
 */
const SESSION_KEY = "pepticraft.builder-session.v2"
const LEGACY_SESSION_KEY = "pepticraft.builder-session.v1"

interface BuildIdentity {
  id: string
  title: string
}

/** The identity of a build together with where it had got to. */
interface BuilderSession extends BuildIdentity {
  step: Step
  route_id: string
  direction: string[]
  scaffold_id: string
  linker_id: string
  thresholds: BuilderThresholds
}

/**
 * The screening thresholds the reader set.
 *
 * The thresholds narrow the candidate set before it is ranked. They can only remove
 * candidates: the library holds twenty million peptides and the candidate set is what the
 * pipeline already screened, so no threshold here brings a new peptide in.
 *
 * A direction is in `functional_floor` when its floor is switched on. Nothing is set by
 * default, so a build that sets no threshold ranks exactly what it always ranked.
 */
interface BuilderThresholds {
  functional_floor: Record<string, number>
  max_allergenicity: number | null
  min_peptide_length: number | null
  max_peptide_length: number | null
  per_direction_limit: number | null
}

/** Read the thresholds out of a stored session, ignoring anything unreadable. */
function readStoredThresholds(raw: unknown): BuilderThresholds {
  const empty: BuilderThresholds = {
    functional_floor: {},
    max_allergenicity: null,
    min_peptide_length: null,
    max_peptide_length: null,
    per_direction_limit: null,
  }
  if (!raw || typeof raw !== "object") return empty
  const stored = raw as Partial<BuilderThresholds>
  const floor: Record<string, number> = {}
  if (stored.functional_floor && typeof stored.functional_floor === "object") {
    for (const [direction, value] of Object.entries(stored.functional_floor)) {
      if (typeof value === "number" && Number.isFinite(value)) floor[direction] = value
    }
  }
  const numberOrNull = (value: unknown): number | null =>
    typeof value === "number" && Number.isFinite(value) ? value : null
  return {
    functional_floor: floor,
    max_allergenicity: numberOrNull(stored.max_allergenicity),
    min_peptide_length: numberOrNull(stored.min_peptide_length),
    max_peptide_length: numberOrNull(stored.max_peptide_length),
    per_direction_limit: numberOrNull(stored.per_direction_limit),
  }
}

function newSessionId(): string {
  const cryptoApi = globalThis.crypto
  if (cryptoApi && typeof cryptoApi.randomUUID === "function") return cryptoApi.randomUUID()
  return `session-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

/** "Build · Nov 3 23:48" - a name that says when, for a build nobody has named yet. */
function defaultSessionTitle(): string {
  const now = new Date()
  return `Build · ${now.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })} ${now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`
}

/** A build that has not been started yet: a fresh name, and nothing chosen. */
function newSession(): BuilderSession {
  return {
    id: newSessionId(),
    title: defaultSessionTitle(),
    step: 1,
    route_id: "",
    direction: [],
    scaffold_id: "",
    linker_id: "",
    thresholds: {
      functional_floor: {},
      max_allergenicity: null,
      min_peptide_length: null,
      max_peptide_length: null,
      per_direction_limit: null,
    },
  }
}

function readSession(): BuilderSession | null {
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<BuilderSession>
    if (typeof parsed.id !== "string" || typeof parsed.title !== "string" || !parsed.title) {
      return null
    }
    const step = typeof parsed.step === "number" ? parsed.step : 1
    return {
      id: parsed.id,
      title: parsed.title,
      step: (step >= 1 && step <= STEP_COUNT ? step : 1) as Step,
      route_id: typeof parsed.route_id === "string" ? parsed.route_id : "",
      direction: Array.isArray(parsed.direction) ? parsed.direction.filter((id) => typeof id === "string") : [],
      scaffold_id: typeof parsed.scaffold_id === "string" ? parsed.scaffold_id : "",
      linker_id: typeof parsed.linker_id === "string" ? parsed.linker_id : "",
      thresholds: readStoredThresholds(parsed.thresholds),
    }
  } catch {
    return null
  }
}

function writeSession(session: BuilderSession): void {
  try {
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
    // The v1 key held a name and nothing else. Left behind, it would be a stale name that
    // nothing reads.
    window.sessionStorage.removeItem(LEGACY_SESSION_KEY)
  } catch {
    // A browser that refuses session storage still gets a working build; the name just does
    // not survive a reload, which is the lesser of the two failures.
  }
}

export default function BuilderPage() {
  const [params, setParams] = useSearchParams()

  /**
   * Which build this page is.
   *
   * Three arrivals reach this page and they mean different things. "Start Building" carries
   * `new`, and wants a build of its own - a fresh name rather than the last one, and no
   * choices carried over. A history record carries `record`, and wants to be put back
   * together. Anything else - a reload, a step away and back - continues the build this tab
   * was already on.
   */
  const [boot] = useState(() => {
    const fresh = params.get("new") === "1"
    const stored = fresh ? null : readSession()
    return { session: stored ?? newSession(), fresh, named: Boolean(stored) }
  })

  const [step, setStep] = useState<Step>(boot.session.step)

  const [routeId, setRouteId] = useState(boot.session.route_id)
  const [directionIds, setDirectionIds] = useState<string[]>(boot.session.direction)
  const [scaffoldId, setScaffoldId] = useState(boot.session.scaffold_id)
  const [linkerId, setLinkerId] = useState(boot.session.linker_id)
  const [thresholds, setThresholds] = useState<BuilderThresholds>(
    boot.session.thresholds ?? newSession().thresholds,
  )
  const [formFilter, setFormFilter] = useState<MaterialForm | "all">("all")

  // Step 4 carries two long passages about how the linker order is decided and what choosing
  // one does not change. Both are true and both are qualifications rather than instructions,
  // so they sit behind a single control the reader opens when the reasoning is wanted.
  const [linkerNotesOpen, setLinkerNotesOpen] = useState(false)

  // The name of the build in progress. Every build that reaches its results is recorded
  // under it, so it is asked for before the choices are made rather than after them.
  const [session, setSession] = useState<BuildIdentity>(boot.session)
  const [nameOpen, setNameOpen] = useState(!boot.named)

  // A record asked for from the history panel, by id. The parameters are applied once the
  // library has arrived, because whether the record's route still exists decides which step
  // it can be reopened on.
  const [pendingRecord, setPendingRecord] = useState<string | null>(() => params.get("record"))

  const load = useCallback(async () => {
    const [reference, scaffolds, linkers] = await Promise.all([
      fetchReference(),
      fetchScaffolds(),
      fetchLinkers(),
    ])
    return { reference, scaffolds, linkers }
  }, [])

  const { data, loading, error, reload } = useAsync(load, [])

  const reference = data?.reference ?? null
  // Held in fetch state, so the identity is stable across renders; every derivation below only
  // recomputes when a new response actually lands.
  const scaffolds = useMemo(() => data?.scaffolds ?? [], [data])
  const linkers = useMemo(() => data?.linkers ?? [], [data])

  const routes = useMemo(() => reference?.routes ?? [], [reference])
  const directions = reference?.directions ?? []
  const labels = materialFormLabels(reference)

  const routeObj = routes.find((route) => route.id === routeId) ?? null
  const scaffoldsByRoute = useMemo(() => groupScaffoldsByRoute(scaffolds), [scaffolds])
  const candidates = useMemo(
    () => (routeObj ? (scaffoldsByRoute.get(routeObj.id) ?? []) : []),
    [routeObj, scaffoldsByRoute],
  )
  const forms = useMemo(() => distinctForms(candidates), [candidates])
  const visibleCandidates =
    formFilter === "all"
      ? candidates
      : candidates.filter((scaffold) => scaffold.material_forms.includes(formFilter))
  const selectedScaffold = scaffolds.find((scaffold) => scaffold.id === scaffoldId) ?? null

  // The linker library is short, is not narrowed by the route, and is the one choice on this
  // page a user has no basis for making from nothing - so the first entry stands in until an
  // explicit choice is made, rather than blocking the step on a click. That the first entry is
  // the library's own recommendation is what makes the fallback defensible rather than
  // arbitrary: the list arrives in recommendation order, most suitable first. Deriving it here
  // keeps the fallback out of an effect and out of state.
  const effectiveLinkerId = linkerId || linkers[0]?.id || ""
  const selectedLinker = linkers.find((linker) => linker.id === effectiveLinkerId) ?? null

  const selectRoute = (route: DeliveryRoute) => {
    if (route.id === routeId) return
    setRouteId(route.id)
    setFormFilter("all")
    const admitted = scaffoldsByRoute.get(route.id) ?? []
    setScaffoldId(admitted[0]?.id ?? "")
  }

  const toggleDirection = (id: string) => {
    setDirectionIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )
  }

  /** Begin again: a new name, and none of the choices that were on screen. */
  const startFresh = useCallback(() => {
    setSession(newSession())
    setStep(1)
    setRouteId("")
    setDirectionIds([])
    setScaffoldId("")
    setLinkerId("")
    setThresholds(newSession().thresholds)
    setFormFilter("all")
    setNameOpen(true)
  }, [])

  // Where the build stands, for this tab. A reload is not a new build, so the name and the
  // step survive one; a construct opened from step 5 and closed again comes back to it.
  useEffect(() => {
    writeSession({
      id: session.id,
      title: session.title,
      step,
      route_id: routeId,
      direction: directionIds,
      scaffold_id: scaffoldId,
      linker_id: linkerId,
      thresholds,
    })
  }, [session, step, routeId, directionIds, scaffoldId, linkerId, thresholds])

  // The address is read once for the two requests it can carry, and both are taken out of
  // it afterwards: a reload repeats neither a new build nor a record that was reopened.
  useEffect(() => {
    const fresh = params.get("new") === "1"
    const record = params.get("record")
    if (!fresh && !record) return
    const next = new URLSearchParams(params)
    next.delete("new")
    next.delete("record")
    setParams(next, { replace: true })
    if (record) {
      setPendingRecord(record)
      return
    }
    // A fresh start was already made while this page was mounting; only a second press,
    // with the page already on screen, has to be acted on here.
    if (!boot.fresh) startFresh()
  }, [params, setParams, boot.fresh, startFresh])

  // Reopening a record. Its own session and name are adopted, so running it again refreshes
  // that record instead of filing a second copy under the name of whatever was on screen.
  useEffect(() => {
    if (!pendingRecord || !data) return
    const record = listBuildRecords().find((item) => item.id === pendingRecord)
    setPendingRecord(null)
    if (!record) return
    setSession((current) => ({ ...current, id: record.session_id, title: record.title }))
    setRouteId(record.params.route_id)
    setDirectionIds(record.params.direction)
    setScaffoldId(record.params.scaffold_id ?? "")
    setLinkerId(record.params.linker_id ?? "")
    setFormFilter("all")
    setNameOpen(false)
    // A record names a route that the library may no longer carry. The rest of its
    // parameters still apply, but the results step needs a route to render under, so an
    // unknown one sends the reader back to the first step to choose a live route.
    setStep(routes.some((route) => route.id === record.params.route_id) ? 5 : 1)
  }, [pendingRecord, data, routes])

  // A build restored from this tab can point at a route the library no longer carries. The
  // results step needs one to render under, so such a build falls back to the first step
  // rather than to a page with nothing on it.
  useEffect(() => {
    if (!data || pendingRecord || step !== 5 || routeObj) return
    setStep(1)
  }, [data, pendingRecord, step, routeObj])

  const applyName = (title: string) => {
    const name = title.trim() || defaultSessionTitle()
    setSession((current) => ({ ...current, title: name }))
    setNameOpen(false)
  }

  // Renaming the build renames the lines it already has in the history, so the header and
  // the record never describe the same build under two names.
  useEffect(() => {
    renameSession(session.id, session.title)
  }, [session.id, session.title])

  /**
   * Write a build into the history.
   *
   * Called from the results step once a build has landed, with the parameters that produced
   * it rather than with the page's current state: the two are the same at that moment, and
   * a record has to describe its own build even after the choices move on. The session is
   * what the record is filed under, so re-running a combination inside one build refreshes
   * that line, while the same combination started again becomes its own.
   */
  const handleRecord = (input: {
    params: BuildRecord["params"]
    labels: BuildRecord["labels"]
    counts: BuildCounts
    total: number
    candidates: Parameters<typeof recordBuild>[0]["candidates"]
  }) => {
    return recordBuild({ session_id: session.id, title: session.title, ...input })
  }

  const canProceed = (target: number) => {
    if (target === 1) return Boolean(routeId)
    if (target === 2) return directionIds.length > 0
    if (target === 3) return Boolean(scaffoldId)
    if (target === 4) return Boolean(effectiveLinkerId)
    return true
  }

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <CardGridSkeleton cards={6} columns={3} />
      </div>
    )
  }

  if (error || !reference) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {error && <ErrorState error={error} onRetry={reload} />}
      </div>
    )
  }

  // A helper rather than a component. It holds no state, and a component defined inside the
  // render body is given a new identity on every pass, which the static check flags; calling
  // it as a function keeps the returned tree part of this component's own render instead.
  const crumb = () =>
    step > 1 ? (
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <button
          onClick={() => setStep((current) => (current - 1) as Step)}
          className="text-sm text-primary-500 hover:text-primary-700 flex items-center gap-1 cursor-pointer"
        >
          <ChevronRight className="w-4 h-4 rotate-180" /> Back
        </button>
        <span className="text-gray-300">|</span>
        <span className="text-sm text-primary-600">
          <strong>{routeObj?.name}</strong>
          {directionIds.length > 0 && (
            <>
              {" · "}
              <strong>
                {directions
                  .filter((direction) => directionIds.includes(direction.id))
                  .map((direction) => direction.name)
                  .join(" + ")}
              </strong>
            </>
          )}
          {selectedScaffold && step >= 4 && (
            <>
              {" · "}
              <strong>{selectedScaffold.short_name}</strong>
            </>
          )}
          {selectedLinker && step >= 5 && (
            <>
              {" · "}
              <strong>{selectedLinker.name}</strong>
            </>
          )}
        </span>
      </div>
    ) : null

  return (
    <div className="min-h-[calc(100vh-8rem)]">
      <section className="gradient-hero border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <div>
            <Badge variant="accent" className="mb-3">
              Construct Builder
            </Badge>
            <h1 className="text-2xl sm:text-3xl font-bold text-primary-900">
              Build Your Construct
            </h1>
            <p className="text-sm text-gray-500 mt-1 max-w-3xl leading-relaxed">
              One choice drives everything - your application route decides which scaffolds stay
              eligible, how they are screened, and how the results are ranked.
            </p>
            {/* On the results step the build's name is the heading, so it is not repeated
                here as a smaller line above it. */}
            {step < 5 && (
              <button
                type="button"
                onClick={() => setNameOpen(true)}
                className="mt-2 inline-flex items-center gap-1.5 text-xs text-primary-600 hover:text-primary-800 cursor-pointer"
                title="Rename this build"
              >
                <span className="font-semibold">{session.title}</span>
                <span className="text-gray-400">· rename</span>
              </button>
            )}
          </div>
        </div>
      </section>

      <BuilderJourney
        step={step}
        route={routeObj?.name}
        functions={directions.filter(direction => directionIds.includes(direction.id)).map(direction => direction.name)}
        scaffold={selectedScaffold?.short_name}
        linker={selectedLinker?.name}
        onBack={target => setStep(target as Step)}
      />

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {step === 1 && (
          <RouteStep
            routes={routes}
            scaffoldsByRoute={scaffoldsByRoute}
            selectedRouteId={routeId}
            onSelect={selectRoute}
            onNext={() => setStep(2)}
            canProceed={canProceed(1)}
          />
        )}

        {step === 2 && (
          <div>
            {crumb()}
            <h2 className="text-lg font-semibold text-primary-900 mb-2">
              Step 2: Select Function Directions
            </h2>
            <p className="text-sm text-gray-500 mb-4 max-w-3xl leading-relaxed">
              Choose the functions you want your peptide to have. You can select more than one.
            </p>

            <div className="grid sm:grid-cols-2 gap-3">
              {directions.map((direction) => (
                <DirectionOption
                  key={direction.id}
                  direction={direction}
                  selected={directionIds.includes(direction.id)}
                  onToggle={() => toggleDirection(direction.id)}
                />
              ))}
            </div>

            {directionIds.length > 0 && (
              <ThresholdPanel
                thresholds={thresholds}
                onChange={setThresholds}
                directions={directions.filter((direction) => directionIds.includes(direction.id))}
                route={routeObj}
                reference={reference.thresholds ?? null}
              />
            )}

            {canProceed(2) && (
              <div className="mt-6 flex justify-end">
                <Button variant="gradient" size="lg" onClick={() => setStep(3)}>
                  Next: Scaffold
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            )}
          </div>
        )}

        {step === 3 && routeObj && (
          <div>
            {crumb()}
            <h2 className="text-lg font-semibold text-primary-900 mb-2">
              Step 3: Scaffold Protein
            </h2>
            <EvidenceLegend />
            <p className="text-sm text-gray-500 mb-1 max-w-3xl leading-relaxed">
              {candidates.length === 0 ? (
                <>
                  No scaffold in the patent dataset is tagged for{" "}
                  <strong>{routeObj.name}</strong>. The route still sets the screening profile;
                  the full library stays selectable under the second tab.
                </>
              ) : (
                <>
                  Already narrowed by <strong>{routeObj.name}</strong> to {candidates.length}{" "}
                  scaffold{candidates.length === 1 ? "" : "s"} - the ones the patent dataset tags
                  for this application.
                </>
              )}
            </p>
            <p className="text-xs text-gray-400 mb-4 max-w-3xl leading-relaxed">
              Material form is a property of each scaffold. Use the chips to filter if you want a
              particular form.
            </p>

            <Notice tone="caution" title="The scaffold is an assembly target, not a filter" className="mb-4">
              Choosing a scaffold here does not narrow the candidate list below: the same
              peptides come back either way. What it changes is the sequence each one is built
              into once the build runs, and the fused length reported beside it. Every stored
              construct already carries a scaffold, assigned by its application route, so this
              step overrides that assignment rather than making the pairing for the first time.
            </Notice>

            <Tabs defaultValue="matched" className="w-full">
              <TabsList>
                <TabsTrigger value="matched">From this route ({candidates.length})</TabsTrigger>
                <TabsTrigger value="all">All scaffolds ({scaffolds.length})</TabsTrigger>
              </TabsList>

              <TabsContent value="matched" className="mt-3">
                {forms.length > 1 && (
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    <FormChip
                      active={formFilter === "all"}
                      onClick={() => setFormFilter("all")}
                      label="All forms"
                    />
                    {forms.map((form) => (
                      <FormChip
                        key={form}
                        active={formFilter === form}
                        onClick={() => setFormFilter(form)}
                        label={formLabel(labels, form)}
                      />
                    ))}
                  </div>
                )}

                <div className="space-y-2">
                  {visibleCandidates.map((scaffold, index) => (
                    <ScaffoldOption
                      key={scaffold.id}
                      scaffold={scaffold}
                      labels={labels}
                      best={formFilter === "all" && index === 0}
                      selected={scaffoldId === scaffold.id}
                      onSelect={() => setScaffoldId(scaffold.id)}
                    />
                  ))}
                  {visibleCandidates.length === 0 && (
                    <p className="text-sm text-gray-400 py-6 text-center">
                      {candidates.length === 0
                        ? "No scaffold carries this route's tag. Pick one from the full library instead."
                        : "No scaffold in this route has that material form."}
                    </p>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="all" className="mt-3 space-y-2">
                {scaffolds.map((scaffold) => (
                  <ScaffoldOption
                    key={scaffold.id}
                    scaffold={scaffold}
                    labels={labels}
                    selected={scaffoldId === scaffold.id}
                    onSelect={() => setScaffoldId(scaffold.id)}
                  />
                ))}
                <p className="text-xs text-gray-400 pt-1">
                  Picking a scaffold outside the route is allowed, but the screening profile above
                  was computed for the route you selected.
                </p>
              </TabsContent>
            </Tabs>

            <div className="mt-6 flex items-center justify-between gap-4">
              <p className="text-xs text-gray-500">
                The next step picks the linker. After that, the build ranks every candidate for
                the selected directions under {routeObj.name}'s screening profile, and assembles
                each one from the scaffold and linker chosen above.
              </p>
              {canProceed(3) && (
                <Button variant="gradient" size="lg" onClick={() => setStep(4)}>
                  Next: Linker
                  <ArrowRight className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>
        )}

        {step === 4 && (
          <div>
            {crumb()}
            <h2 className="text-lg font-semibold text-primary-900 mb-2">Step 4: Linker</h2>
            <p className="text-sm text-gray-500 mb-1 max-w-3xl leading-relaxed">
              The whole library, {linkers.length} entries - the linker sits between the scaffold
              and the peptide, and the route does not narrow this choice. The list is in the
              library's recommendation order, most suitable first, and the entry the reader does
              not change is the one at the top.
            </p>

            <button
              type="button"
              onClick={() => setLinkerNotesOpen((open) => !open)}
              aria-expanded={linkerNotesOpen}
              className="mb-3 inline-flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-800 cursor-pointer"
            >
              {linkerNotesOpen ? "Show less" : "Learn More"}
              <ChevronDown
                className={cn(
                  "w-3.5 h-3.5 transition-transform",
                  linkerNotesOpen && "rotate-180",
                )}
              />
            </button>

            {linkerNotesOpen && (
              <>
                <p className="text-xs text-gray-400 mb-4 max-w-3xl leading-relaxed">
                  The order follows one argument rather than a measurement: a short functional
                  peptide has to stay reachable on the outside of a large structural protein, so
                  flexible Gly-Ser linkers come first - they hold the peptide clear without
                  occluding it and without disturbing the scaffold's own assembly - and the rigid
                  α-helical and proline entries come last, because fixing the geometry is a
                  specialist answer rather than a default. Every entry states why it sits where it
                  does when it is selected. No experiment in the pipeline compared two linkers on
                  one fusion, so the order is a judgement about assembly, not a claim about
                  activity.
                </p>

                <Notice
                  tone="caution"
                  title="The linker is an assembly target, not a filter"
                  className="mb-4"
                >
                  Every stored construct records the same sample-table entry, which the assembly
                  script attached as the first available row rather than chose. Choosing here
                  therefore does not narrow the candidate list below, and it changes no score.
                  What it changes is the sequence each candidate is built into on the next step,
                  and the fused length reported beside it.
                </Notice>
              </>
            )}

            <div className="space-y-2">
              {linkers.map((linker) => (
                <LinkerOption
                  key={linker.id}
                  linker={linker}
                  selected={effectiveLinkerId === linker.id}
                  onSelect={() => setLinkerId(linker.id)}
                />
              ))}
              {linkers.length === 0 && (
                <p className="text-sm text-gray-400 py-6 text-center">
                  The linker library returned nothing, so there is nothing to assemble with.
                </p>
              )}
            </div>

            <div className="mt-6 flex items-center justify-between gap-4">
              <p className="text-xs text-gray-500">
                The next step ranks every candidate for the selected directions under{" "}
                {routeObj?.name ?? "the selected route"}'s screening profile, and assembles each
                one from the scaffold and linker selected here.
              </p>
              {canProceed(4) && (
                <Button variant="gradient" size="lg" onClick={() => setStep(5)}>
                  <FlaskConical className="w-4 h-4" />
                  Build Constructs
                  <ArrowRight className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>
        )}

        {step === 5 && routeObj && (
          <ResultStep
            title={session.title}
            route={routeObj}
            directionIds={directionIds}
            directions={directions}
            thresholds={thresholds}
            scaffold={selectedScaffold}
            linker={selectedLinker}
            onBack={() => setStep(4)}
            onReset={startFresh}
            onRecord={handleRecord}
            onOpenHistory={openHistoryPanel}
          />
        )}
      </div>

      <BuildNameDialog
        open={nameOpen}
        initialValue={session.title}
        onSubmit={applyName}
      />
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 1
// ─────────────────────────────────────────────────────────────────────────────

function RouteStep({
  routes,
  scaffoldsByRoute,
  selectedRouteId,
  onSelect,
  onNext,
  canProceed,
}: {
  routes: DeliveryRoute[]
  scaffoldsByRoute: Map<string, ScaffoldSummary[]>
  selectedRouteId: string
  onSelect: (route: DeliveryRoute) => void
  onNext: () => void
  canProceed: boolean
}) {
  const selected = routes.find((route) => route.id === selectedRouteId) ?? null
  const selectedScaffolds = selected ? (scaffoldsByRoute.get(selected.id) ?? []) : []

  return (
    <div>
      <h2 className="text-lg font-semibold text-primary-900 mb-2">
        Step 1: Choose Your Application Route
      </h2>
      <p className="text-sm text-gray-500 mb-5 max-w-3xl leading-relaxed">
        Every card states which scaffolds are applicable to the corresponding route, how it reweights
        the screening, and the immunogenicity hard-veto it applies.
      </p>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {routes.map((route) => {
          const Icon = iconFor(route.icon)
          const isSelected = selectedRouteId === route.id
          const admitted = scaffoldsByRoute.get(route.id) ?? []
          const tight = route.screening.immunogenicity_threshold <= 0.35

          return (
            <button
              key={route.id}
              onClick={() => onSelect(route)}
              className={cn(
                "text-left p-4 rounded-xl border-2 transition-all duration-200",
                isSelected
                  ? "border-primary-400 bg-primary-50 shadow-sm ring-1 ring-primary-300"
                  : "border-gray-200 hover:border-primary-200 hover:bg-surface-alt cursor-pointer",
              )}
            >
              <div className="flex items-start gap-3">
                <div
                  className={cn(
                    "w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0",
                    isSelected ? "bg-primary-100" : "bg-surface-alt",
                  )}
                >
                  <Icon
                    className={cn("w-5 h-5", isSelected ? "text-primary-600" : "text-primary-400")}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-semibold text-primary-900">{route.name}</span>
                    {route.emerging && (
                      <Badge variant="warning" className="text-[10px]">
                        Evidence building
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                    {route.contact_interface}
                  </p>
                  <div className="flex items-center gap-1.5 mt-2 text-[11px] font-mono text-gray-400 flex-wrap">
                    <span>
                      {admitted.length === 0
                        ? "no scaffold available"
                        : `${admitted.length} scaffold${admitted.length === 1 ? "" : "s"}`}
                    </span>
                    <span>·</span>
                    <span>{route.barrier_label}</span>
                  </div>
                  <div
                    className={cn(
                      "text-[11px] mt-1 font-mono",
                      tight ? "text-amber-600" : "text-gray-400",
                    )}
                  >
                    immuno ≤ {route.screening.immunogenicity_threshold.toFixed(2)}
                  </div>
                </div>
                {isSelected && (
                  <CheckCircle2 className="w-5 h-5 text-primary-500 flex-shrink-0" />
                )}
              </div>
            </button>
          )
        })}
      </div>

      {selected && (
        <div className="mt-5 p-5 rounded-xl border-2 border-accent-200 bg-gradient-to-r from-accent-50 to-white">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg gradient-accent flex items-center justify-center flex-shrink-0">
              <FlaskConical className="w-4 h-4 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-primary-900">
                Choosing “{selected.name}” does three things
              </h3>

              <div className="grid sm:grid-cols-3 gap-5 mt-4">
                <div>
                  <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-2">
                    ① Narrows the scaffold pool
                  </p>
                  <div className="space-y-1.5">
                    {selectedScaffolds.map((scaffold) => (
                      <div key={scaffold.id} className="text-xs">
                        <span className="text-primary-800 font-medium">{scaffold.short_name}</span>
                        {scaffold.max_evidence && (
                          <span className="text-gray-400 ml-1.5 font-mono">
                            {scaffold.max_evidence}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                  <p className="text-[11px] text-gray-400 mt-2">
                    {selectedScaffolds.length} scaffolds admitted by this route
                  </p>
                </div>

                <div>
                  <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-2">
                    ② Resets the screening
                  </p>
                  <dl className="space-y-1 text-xs">
                    <div className="flex justify-between gap-2">
                      <dt className="text-gray-500">Penetration</dt>
                      <dd className="text-primary-800 font-mono text-right">
                        {WEIGHT_TIER_LABEL[selected.screening.cpp_weight]}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-gray-500">Solubility</dt>
                      <dd className="text-primary-800 font-mono text-right">
                        {WEIGHT_TIER_LABEL[selected.screening.solubility_weight]}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-gray-500">Thermal</dt>
                      <dd className="text-primary-800 font-mono text-right">
                        {WEIGHT_TIER_LABEL[selected.screening.thermal_stability_weight]}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2 pt-1 border-t border-gray-200">
                      <dt className="text-gray-500">Immunogenicity</dt>
                      <dd className="text-amber-600 font-mono text-right">
                        ≤ {selected.screening.immunogenicity_threshold.toFixed(2)}
                      </dd>
                    </div>
                  </dl>
                  <p className="text-[11px] text-gray-400 mt-2 leading-relaxed">
                    {selected.screening.threshold_note}
                  </p>
                </div>

                <div>
                  <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-2">
                    ③ Typical application
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.application_techniques.map((technique) => (
                      <span
                        key={technique}
                        className="text-[11px] px-1.5 py-0.5 rounded bg-white border border-gray-200 text-gray-500"
                      >
                        {technique}
                      </span>
                    ))}
                  </div>
                  <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mt-3 mb-1.5">
                    Extra gates
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.screening.extra_gates.map((gate) => (
                      <span
                        key={gate}
                        className="text-[11px] px-1.5 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-700"
                      >
                        {gate}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {selected?.emerging && selected.emerging_note && (
        <Notice tone="caution" title="Evidence behind this route is still accumulating" className="mt-3">
          {selected.emerging_note}
        </Notice>
      )}

      {canProceed && (
        <div className="mt-6 flex justify-end">
          <Button variant="gradient" size="lg" onClick={onNext}>
            Next: Function Direction
            <ArrowRight className="w-4 h-4" />
          </Button>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 2
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Step 2 — screening thresholds
// ─────────────────────────────────────────────────────────────────────────────

/**
 * A switch that looks like a switch.
 */
function KnobSwitch({
  on,
  onChange,
  label,
}: {
  on: boolean
  onChange: (next: boolean) => void
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => onChange(!on)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-200 cursor-pointer",
        on ? "bg-primary-500" : "bg-gray-300",
      )}
    >
      <span
        className={cn(
          "flex h-4 w-4 items-center justify-center rounded-full bg-white shadow-sm transition-transform duration-200",
          on ? "translate-x-[1rem]" : "translate-x-[0.125rem]",
        )}
      />
    </button>
  )
}

/**
 * A number with a dial beside it.
 *
 * The dial gives the scale and the field lets an exact value be typed, which matters because
 * the boundaries the predictors declare are not round numbers. Both write the same value, so
 * neither is the one that is authoritative.
 */
function Dial({
  value,
  min,
  max,
  step,
  accent,
  onChange,
  label,
}: {
  value: number
  min: number
  max: number
  step: number
  accent: string
  onChange: (next: number) => void
  label: string
}) {
  const fill = max > min ? ((value - min) / (max - min)) * 100 : 0
  return (
    <div className="flex items-center gap-3">
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={`${label} dial`}
        onChange={(event) => onChange(Number(event.target.value))}
        className="knob min-w-[7rem] flex-1"
        style={{ "--fill": fill, "--accent": accent } as CSSProperties}
      />
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={label}
        onChange={(event) => onChange(Number(event.target.value))}
        className="num-field h-9 w-[4.5rem] shrink-0 rounded-lg border border-gray-200 bg-white px-2.5 text-center font-mono text-sm tabular-nums text-primary-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-200"
      />
    </div>
  )
}

/**
 * One threshold, as a card of its own.
 *
 * The icon carries the threshold's colour and the card takes that colour when the threshold
 * is on, so which thresholds are in force is readable without reading any of them.
 *
 * A threshold that governs several things at once carries no switch of its own: each of the
 * things it governs has a switch, and a second switch over them would only be able to lie
 * about the ones in between.
 */
function ThresholdBlock({
  icon: Icon,
  accent,
  title,
  hint,
  tip,
  active,
  badge,
  toggle,
  reveal = "whenActive",
  children,
}: {
  icon: LucideIcon
  accent: string
  title: string
  hint: string
  /** An explanation of the term, shown beside the title. */
  tip?: string
  /** Whether the threshold is in force. Decides whether the card is filled or bare. */
  active: boolean
  /** A short note on the right, beside the switch. */
  badge?: string
  /** The card's own switch, absent when the threshold governs several things separately. */
  toggle?: { on: boolean; onChange: (next: boolean) => void; label: string }
  /** Whether the card's contents are shown. */
  reveal?: "whenActive" | "always"
  children?: ReactNode
}) {
  return (
    <div
      className={cn(
        "rounded-xl border transition-all duration-200",
        active ? "border-gray-200 bg-white shadow-sm" : "border-gray-200 bg-white/50",
      )}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <span
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors duration-200",
            active ? "text-white shadow-sm" : "bg-gray-100 text-gray-400",
          )}
          style={active ? { backgroundColor: accent } : undefined}
        >
          <Icon className="h-[18px] w-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-primary-900">
            {title}
            {tip && <InfoTip content={tip} className="ml-1 align-middle" />}
          </p>
          <p className="text-xs text-gray-500">{hint}</p>
        </div>
        {badge && (
          <span className="shrink-0 text-xs tabular-nums text-gray-400">{badge}</span>
        )}
        {toggle && (
          <KnobSwitch on={toggle.on} onChange={toggle.onChange} label={toggle.label} />
        )}
      </div>
      {(active || reveal === "always") && children ? (
        <div className="border-t border-gray-100 px-4 py-3">{children}</div>
      ) : null}
    </div>
  )
}

/**
 * The screening thresholds, folded into the step that chooses the functions.
 *
 * They are not a step of their own because they are not another decision: a threshold narrows
 * the candidates the chosen functions already produced, and it changes nothing about the
 * scaffold, the linker or the sequence. A step of their own would put a filter in the middle
 * of a flow that assembles.
 *
 * Each threshold shows the value its own predictor declares, so nobody is asked to guess what
 * a meaningful number looks like. Nothing is set until it is switched on, so a build that
 * leaves the panel alone ranks exactly what it always ranked.
 */
function ThresholdPanel({
  thresholds,
  onChange,
  directions,
  route,
  reference,
}: {
  thresholds: BuilderThresholds
  onChange: (next: BuilderThresholds) => void
  /** The functions the reader is holding. A floor is offered per function. */
  directions: FunctionDirection[]
  /** The application route this build runs under. It owns the immunogenicity gate. */
  route: DeliveryRoute | null
  reference: ThresholdReference | null
}) {
  const [open, setOpen] = useState(false)
  const functionalReference = reference?.functional_score ?? {}
  const allergenicityReference = reference?.allergenicity
  const lengthReference = reference?.peptide_length

  const set = <K extends keyof BuilderThresholds>(
    key: K,
    value: BuilderThresholds[K],
  ) => onChange({ ...thresholds, [key]: value })

  /** Switch one direction's score floor on or off, keeping its value either way. */
  const toggleFloor = (direction: string, on: boolean) => {
    const floor = { ...thresholds.functional_floor }
    if (on) {
      const declared = functionalReference[direction]?.declared_boundary ?? 0
      floor[direction] = floor[direction] ?? declared
    } else {
      delete floor[direction]
    }
    set("functional_floor", floor)
  }

  // A floor is offered only where the direction's score measures activity. The two
  // ranking-only directions are named in the note below instead, because a control that
  // does nothing would read as one that does.
  const floorDirections = directions.filter(
    (direction) => functionalReference[direction.id]?.floor_applies !== false,
  )
  const rankingOnly = directions.filter(
    (direction) => functionalReference[direction.id]?.floor_applies === false,
  )
  const floorsOn = floorDirections.filter(
    (direction) => thresholds.functional_floor[direction.id] !== undefined,
  )

  const setCount =
    Object.keys(thresholds.functional_floor).length +
    (thresholds.max_allergenicity !== null ? 1 : 0) +
    (thresholds.min_peptide_length !== null || thresholds.max_peptide_length !== null ? 1 : 0) +
    (thresholds.per_direction_limit !== null ? 1 : 0)

  const lengthOn =
    thresholds.min_peptide_length !== null || thresholds.max_peptide_length !== null

  return (
    <div
      className="mt-4 rounded-2xl border border-gray-200 bg-surface-alt/60 shadow-sm"
      data-panel-body="thresholds"
    >
      <div className="flex items-center gap-2 px-4 py-3">
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          aria-expanded={open}
          data-panel="thresholds"
          className="flex flex-1 cursor-pointer items-center gap-2.5 text-left"
        >
          <ChevronDown
            className={cn(
              "h-4 w-4 text-gray-400 transition-transform duration-200",
              open && "rotate-180",
            )}
          />
          <span className="text-sm font-semibold text-primary-900">Screening thresholds</span>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[11px] font-medium",
              setCount === 0
                ? "bg-gray-200 text-gray-500"
                : "bg-primary-100 text-primary-700",
            )}
          >
            {setCount === 0 ? "none set" : `${setCount} set`}
          </span>
        </button>
        <InfoTip content={GLOSSARY.screening_thresholds} />
      </div>

      {open && (
        <div className="space-y-3 px-4 pb-4">
          <p className="text-xs leading-relaxed text-gray-500">
            These narrow the candidates before they are ranked. They can only remove candidates:
            the peptide library holds twenty million sequences and these act on the ones the
            pipeline has already screened.
          </p>

          {/* The route's own immunogenicity gate, stated where the thresholds are read.
              It is not one of the four thresholds below and it is not adjustable here: the
              route owns it, and it is applied to every candidate in the build whether or not
              this panel is touched. It is shown because a gate that varies by application
              route and a fixed number in the same panel read as the same thing, and the two
              are different predictors on different scales. */}
          {route && (
            <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-3">
              <div className="flex items-start gap-3">
                <Shield className="mt-0.5 h-[18px] w-[18px] shrink-0 text-amber-600" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-primary-900">
                    Immunogenicity gate (MHC-I)
                    <InfoTip content={GLOSSARY.immunogenicity_gate} className="ml-1 align-middle" />
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-gray-600">
                    Set by the application route — {route.name} — and already applied to every
                    candidate in this build. It is not adjustable here, because the route owns
                    it.
                  </p>
                  <p className="mt-2 font-mono text-sm tabular-nums text-amber-700">
                    MHC-I ≤ {route.screening.immunogenicity_threshold.toFixed(2)}
                  </p>
                  <p className="mt-1.5 text-[11px] leading-relaxed text-gray-500">
                    {route.screening.threshold_note}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Score floor, one per function whose score is a probability. The block has no
              switch of its own: each function below carries one, and a switch over all of
              them could not say which of them were on. */}
          {floorDirections.length > 0 && (
            <ThresholdBlock
              icon={Activity}
              accent="#0ea5e9"
              title="Activity score floor"
              hint="The lowest score a candidate may have"
              active={floorsOn.length > 0}
              reveal="always"
              badge={
                floorsOn.length > 0
                  ? `${floorsOn.length} of ${floorDirections.length} set`
                  : undefined
              }
            >
              <div className="space-y-1">
                {floorDirections.map((direction) => {
                  const entry = functionalReference[direction.id]
                  const value = thresholds.functional_floor[direction.id]
                  const on = value !== undefined
                  const pool = direction.counts?.top ?? 0
                  const accent = direction.color ?? "#0ea5e9"
                  return (
                    <div
                      key={direction.id}
                      className="flex flex-wrap items-center gap-x-3 gap-y-2 py-1.5"
                    >
                      <KnobSwitch
                        on={on}
                        onChange={(next) => toggleFloor(direction.id, next)}
                        label={`${direction.name} activity score floor`}
                      />
                      <span className="w-32 shrink-0 text-sm font-medium text-primary-900">
                        {direction.name}
                      </span>
                      <div className="w-full max-w-md">
                        {on ? (
                          <Dial
                            value={value}
                            min={0}
                            max={1}
                            step={0.01}
                            accent={accent}
                            label={`${direction.name} activity score floor`}
                            onChange={(next) =>
                              set("functional_floor", {
                                ...thresholds.functional_floor,
                                [direction.id]: next,
                              })
                            }
                          />
                        ) : (
                          <span className="text-xs text-gray-400">not set</span>
                        )}
                      </div>
                      <span className="w-56 shrink-0 text-right text-xs tabular-nums text-gray-400">
                        {entry?.declared_boundary !== null && entry?.declared_boundary !== undefined
                          ? `boundary ${entry.declared_boundary.toFixed(2)}`
                          : "no boundary declared"}
                        {` · ${pool} candidates`}
                      </span>
                    </div>
                  )
                })}
              </div>
            </ThresholdBlock>
          )}

          {rankingOnly.length > 0 && (
            <p className="px-1 text-[11px] leading-relaxed text-gray-400">
              {rankingOnly.map((direction) => direction.name).join(" and ")}{" "}
              {rankingOnly.length === 1 ? "is" : "are"} ranked by a score that orders
              candidates rather than measuring activity, so no floor applies to
              {rankingOnly.length === 1 ? " it" : " them"}. Use the candidates per function cap
              instead.
            </p>
          )}

          {/* Allergenicity ceiling. Named after the predictor that produces it, because
              "allergenicity" and "immunogenicity" are two different risks measured by two
              different predictors, and only the second one varies with the route. */}
          <ThresholdBlock
            icon={ShieldAlert}
            accent="#f59e0b"
            title={`${allergenicityReference?.tool ?? "AlgPred2"} allergenicity ceiling`}
            hint="the lower the value the safer the peptide · a different predictor from the route's immunogenicity gate"
            tip={GLOSSARY.allergenicity_ceiling}
            active={thresholds.max_allergenicity !== null}
            badge={
              allergenicityReference
                ? `boundary ${allergenicityReference.boundary.toFixed(2)}`
                : undefined
            }
            toggle={{
              on: thresholds.max_allergenicity !== null,
              onChange: (next) =>
                set("max_allergenicity", next ? (allergenicityReference?.boundary ?? 0.3) : null),
              label: "AlgPred2 allergenicity ceiling",
            }}
          >
            {thresholds.max_allergenicity !== null && (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                {/* A dial of a fixed width, so it reads as one control rather than as a
                    rule stretched across the panel. */}
                <div className="w-full max-w-md">
                  <Dial
                    value={thresholds.max_allergenicity}
                    min={0}
                    max={1}
                    step={0.01}
                    accent="#f59e0b"
                    label="AlgPred2 allergenicity ceiling"
                    onChange={(next) => set("max_allergenicity", next)}
                  />
                </div>
              </div>
            )}
          </ThresholdBlock>

          {/* Peptide length range. */}
          <ThresholdBlock
            icon={Ruler}
            accent="#8b5cf6"
            title="Peptide length"
            hint="Residues of the peptide on its own, before the scaffold and the linker"
            active={lengthOn}
            badge={
              lengthReference
                ? `${lengthReference.min}–${lengthReference.max} aa in the library`
                : undefined
            }
            toggle={{
              on: lengthOn,
              onChange: (next) =>
                onChange({
                  ...thresholds,
                  min_peptide_length: next ? (lengthReference?.min ?? 1) : null,
                  max_peptide_length: next ? (lengthReference?.max ?? 30) : null,
                }),
              label: "Peptide length",
            }}
          >
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="number"
                min={lengthReference?.min ?? 1}
                max={lengthReference?.max ?? 30}
                placeholder={String(lengthReference?.min ?? 1)}
                value={thresholds.min_peptide_length ?? ""}
                onChange={(event) =>
                  set(
                    "min_peptide_length",
                    event.target.value === "" ? null : Number(event.target.value),
                  )
                }
                aria-label="Shortest peptide to keep"
                className="num-field h-9 w-[4.5rem] rounded-lg border border-gray-200 bg-white px-2.5 text-center font-mono text-sm tabular-nums text-primary-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-200"
              />
              <span className="text-xs text-gray-400">to</span>
              <input
                type="number"
                min={lengthReference?.min ?? 1}
                max={lengthReference?.max ?? 30}
                placeholder={String(lengthReference?.max ?? 30)}
                value={thresholds.max_peptide_length ?? ""}
                onChange={(event) =>
                  set(
                    "max_peptide_length",
                    event.target.value === "" ? null : Number(event.target.value),
                  )
                }
                aria-label="Longest peptide to keep"
                className="num-field h-9 w-[4.5rem] rounded-lg border border-gray-200 bg-white px-2.5 text-center font-mono text-sm tabular-nums text-primary-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-200"
              />
              <span className="text-xs text-gray-400">residues</span>
            </div>
          </ThresholdBlock>

          {/* Per-direction cap. */}
          <ThresholdBlock
            icon={Layers}
            accent="#10b981"
            title="Candidates per function"
            hint="How many each function contributes to the ranking"
            active={thresholds.per_direction_limit !== null}
            toggle={{
              on: thresholds.per_direction_limit !== null,
              onChange: (next) => set("per_direction_limit", next ? 10 : null),
              label: "Candidates per function",
            }}
          >
            {thresholds.per_direction_limit !== null && (
              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={thresholds.per_direction_limit}
                  onChange={(event) => set("per_direction_limit", Number(event.target.value))}
                  aria-label="Candidates each function contributes"
                  className="num-field h-9 w-[4.5rem] rounded-lg border border-gray-200 bg-white px-2.5 text-center font-mono text-sm tabular-nums text-primary-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-200"
                />
                <span className="text-xs text-gray-400">
                  counted within each function&apos;s own order
                </span>
              </div>
            )}
          </ThresholdBlock>

          {setCount > 0 && (
            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={() =>
                  onChange({
                    functional_floor: {},
                    max_allergenicity: null,
                    min_peptide_length: null,
                    max_peptide_length: null,
                    per_direction_limit: null,
                  })
                }
                className="cursor-pointer rounded-lg px-2.5 py-1 text-xs font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-primary-800"
              >
                Clear all thresholds
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DirectionOption({
  direction,
  selected,
  onToggle,
}: {
  direction: FunctionDirection
  selected: boolean
  onToggle: () => void
}) {
  const Icon = iconFor(direction.icon, ShieldAlert)
  const unavailable = direction.status === "empty"

  return (
    <button
      onClick={onToggle}
      disabled={unavailable}
      className={cn(
        "text-left p-4 rounded-xl border-2 transition-all duration-200",
        unavailable
          ? "border-gray-100 bg-surface-alt opacity-50 cursor-not-allowed"
          : selected
            ? "border-primary-400 bg-primary-50 shadow-sm ring-1 ring-primary-300"
            : "border-gray-200 hover:border-primary-200 hover:bg-surface-alt cursor-pointer",
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: `${direction.color}15` }}
        >
          <Icon className="w-5 h-5" style={{ color: direction.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-primary-900">{direction.name}</span>
            <Badge
              variant={direction.status === "ready" ? "accent" : "warning"}
              className="text-xs"
            >
              {DIRECTION_STATUS_LABEL[direction.status] ?? direction.status}
            </Badge>
          </div>
          <p className="text-xs text-gray-500 mt-1 leading-relaxed">{direction.description}</p>
          <div className="flex flex-wrap gap-2 mt-1.5 text-xs text-gray-400 font-mono">
            <span>{direction.precursor_count.toLocaleString()} peptides</span>
            <span>·</span>
            <span>{direction.construct_count} constructs</span>
          </div>
        </div>
        {selected && <CheckCircle2 className="w-5 h-5 text-primary-500 flex-shrink-0" />}
      </div>

      {direction.status === "wip" && (
        <p className="text-[11px] text-amber-700 mt-2 leading-relaxed">
          The pipeline has not signed these rows off. They can be included, and every result keeps
          the marker.
        </p>
      )}
    </button>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 3
// ─────────────────────────────────────────────────────────────────────────────

function ScaffoldOption({
  scaffold,
  labels,
  best,
  selected,
  onSelect,
}: {
  scaffold: ScaffoldSummary
  labels: Record<string, string>
  best?: boolean
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full text-left p-4 rounded-xl border-2 transition-all duration-200",
        selected
          ? "border-primary-400 bg-primary-50 shadow-sm"
          : "border-gray-200 hover:border-primary-200 hover:bg-surface-alt cursor-pointer",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-primary-900">{scaffold.short_name}</span>
            {scaffold.length !== null && (
              <Badge variant="secondary" className="text-xs">
                {scaffold.length} aa
              </Badge>
            )}
            {scaffold.max_evidence && (
              <Badge variant="accent" className="text-xs">
                Evidence {scaffold.max_evidence}
              </Badge>
            )}
            {best && (
              <Badge variant="accent" className="text-xs">
                Best match
              </Badge>
            )}
            {!scaffold.has_sequence && (
              <Badge variant="warning" className="text-xs">
                no sequence
              </Badge>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-1">{scaffold.applicant}</p>
          {scaffold.material_forms.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {scaffold.material_forms.map((form) => (
                <span
                  key={form}
                  className="text-[11px] px-1.5 py-0.5 rounded bg-surface-alt border border-gray-200 text-gray-500"
                >
                  {formLabel(labels, form)}
                </span>
              ))}
            </div>
          )}
          {scaffold.species && (
            <p className="text-xs text-gray-500 mt-1.5 italic leading-relaxed">
              {scaffold.species}
            </p>
          )}
          {scaffold.patent && (
            <p className="text-xs text-gray-400 mt-1 line-clamp-2">Patent: {scaffold.patent}</p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
          <span className="text-[11px] font-mono text-gray-400">
            {scaffold.sequence_count} seq
          </span>
          {selected && <CheckCircle2 className="w-5 h-5 text-primary-500" />}
        </div>
      </div>
    </button>
  )
}

function FormChip({
  active,
  onClick,
  label,
}: {
  active: boolean
  onClick: () => void
  label: string
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "text-[11px] px-2 py-1 rounded border transition-colors cursor-pointer",
        active
          ? "border-primary-400 bg-primary-50 text-primary-700"
          : "border-gray-200 bg-white text-gray-500 hover:border-primary-200",
      )}
    >
      {label}
    </button>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 4
// ─────────────────────────────────────────────────────────────────────────────

function LinkerOption({
  linker,
  selected,
  onSelect,
}: {
  linker: LinkerView
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full text-left p-4 rounded-xl border-2 transition-all duration-200",
        selected
          ? "border-primary-400 bg-primary-50 shadow-sm"
          : "border-gray-200 hover:border-primary-200 hover:bg-surface-alt cursor-pointer",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-primary-900">{linker.name}</span>
            <Badge variant="secondary" className="text-xs">
              {linker.length} aa
            </Badge>
            <Badge variant="outline" className="text-xs">
              {linker.rigidity}
            </Badge>
            {/* The list is in recommendation order, so an entry's position is information the
                reader would otherwise have to infer from the sequence of the page. Only the top
                one is called out, and only a ranked entry can be: the sample table's rows are
                not ranked, and one of them may be a reader's stored linker. */}
            {linker.priority_rank === 1 && (
              <Badge variant="accent" className="text-xs">
                Recommended
              </Badge>
            )}
            {linker.priority_rank !== null && linker.priority_rank > 1 && (
              <span className="text-[11px] text-gray-400">#{linker.priority_rank} in order</span>
            )}
          </div>
          <p className="font-mono text-xs text-primary-700 mt-1.5 break-all">{linker.sequence}</p>
          {linker.description && (
            <p className="text-xs text-gray-500 mt-1 leading-relaxed">{linker.description}</p>
          )}
          {/* Why this one sits here, shown for the chosen entry rather than for all fifteen:
              the reason is a paragraph, and fifteen of them at once is a wall. */}
          {selected && linker.priority_reason && (
            <p className="text-xs text-primary-700 mt-2 leading-relaxed border-l-2 border-primary-300 pl-2.5">
              {linker.priority_reason}
            </p>
          )}
          {linker.reference && (
            <p className="text-xs text-gray-400 mt-1 italic leading-relaxed">{linker.reference}</p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
          {/* Which of the two linker tables the entry came from, printed rather than inferred:
              the sample rows are real sequences too, and only this says which set answered. */}
          <span className="text-[11px] font-mono text-gray-400">{linker.source_table}</span>
          {selected && <CheckCircle2 className="w-5 h-5 text-primary-500" />}
        </div>
      </div>
    </button>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 5
// ─────────────────────────────────────────────────────────────────────────────

function ResultStep({
  title,
  route,
  directionIds,
  directions,
  thresholds,
  scaffold,
  linker,
  onBack,
  onReset,
  onRecord,
  onOpenHistory,
}: {
  /** The name this build was started under. It is the heading of the page. */
  title: string
  route: DeliveryRoute
  directionIds: string[]
  directions: FunctionDirection[]
  /** The screening thresholds the reader set in step 2. */
  thresholds: BuilderThresholds
  scaffold: ScaffoldSummary | null
  linker: LinkerView | null
  onBack: () => void
  onReset: () => void
  onRecord: (input: {
    params: BuildRecord["params"]
    labels: BuildRecord["labels"]
    counts: BuildCounts
    total: number
    candidates: Parameters<typeof recordBuild>[0]["candidates"]
  }) => { ok: true; record: BuildRecord; created: boolean } | { ok: false; error: string }
  onOpenHistory: () => void
}) {
  // The parameters travel with the response rather than being read again at write time.
  // A request is in flight for a moment after the choices change, and for that moment the
  // page's own state describes a build that has not arrived - recording from it would file
  // one build's figures under another's choices.
  const load = useCallback(async () => {
    const params = {
      direction: directionIds,
      route_id: route.id,
      scaffold_id: scaffold?.id ?? null,
      linker_id: linker?.id ?? null,
      limit: RESULT_LIMIT,
      min_functional_score: thresholds.functional_floor,
      max_allergenicity: thresholds.max_allergenicity,
      min_peptide_length: thresholds.min_peptide_length,
      max_peptide_length: thresholds.max_peptide_length,
      per_direction_limit: thresholds.per_direction_limit,
    }
    const result = await fetchBuild(params)
    return { params, result }
  }, [directionIds, route.id, scaffold?.id, linker?.id, thresholds])

  const build = useAsync(load, [directionIds, route.id, scaffold?.id, linker?.id, thresholds])
  const data = build.data?.result ?? null
  const loading = build.loading
  const error = build.error
  const reload = build.reload

  const items = data?.items ?? []
  const counts = data?.counts ?? null

  /** What the thresholds the reader set did to the candidate set. */
  const thresholdReport = data?.thresholds ?? null
  const thresholdRemoved =
    (thresholdReport?.removed ?? 0) + (thresholdReport?.removed_by_cap ?? 0)
  const thresholdSetCount =
    Object.keys(thresholds.functional_floor).length +
    (thresholds.max_allergenicity !== null ? 1 : 0) +
    (thresholds.min_peptide_length !== null || thresholds.max_peptide_length !== null ? 1 : 0) +
    (thresholds.per_direction_limit !== null ? 1 : 0)

  const selectedNames = directions
    .filter((direction) => directionIds.includes(direction.id))
    .map((direction) => direction.name)
    .join(" + ")

  // Recording. It happens on arrival rather than on a click: a build that ran is part of
  // the history, and the moment to notice that is when its results appear.
  const [recordError, setRecordError] = useState<string | null>(null)
  const [recorded, setRecorded] = useState<{
    id: string
    at: string
    created: boolean
  } | null>(null)
  const record = useRef(onRecord)
  record.current = onRecord

  useEffect(() => {
    if (!build.data) return
    const outcome = record.current({
      params: build.data.params,
      labels: {
        route: route.name,
        directions: selectedNames,
        scaffold: scaffold?.short_name ?? null,
        linker: linker?.name ?? null,
      },
      counts: build.data.result.counts,
      total: build.data.result.total,
      candidates: build.data.result.items,
    })
    if (outcome.ok) {
      setRecordError(null)
      setRecorded({ id: outcome.record.id, at: new Date().toISOString(), created: outcome.created })
    } else {
      setRecorded(null)
      setRecordError(outcome.error)
    }
    // Only the response can trigger a write. `onRecord` is held in a ref because a new
    // function identity on every parent render would otherwise record the same build again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [build.data])

  return (
    <div>
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <button
          onClick={onBack}
          className="text-sm text-primary-500 hover:text-primary-700 flex items-center gap-1 cursor-pointer"
        >
          <ChevronRight className="w-4 h-4 rotate-180" /> Back
        </button>
      </div>

      {/* The build's name heads its own results. Everything below describes that one build,
          so the name is the page's title rather than a line inside it. */}
      <h1 className="text-2xl sm:text-3xl font-bold text-primary-900 leading-tight break-words">
        {title}
      </h1>
      <p className="text-sm text-gray-500 mt-1.5 mb-5">
        <strong className="font-medium text-primary-700">{route.name}</strong> ·{" "}
        <strong className="font-medium text-primary-700">{selectedNames}</strong>
        {scaffold && (
          <>
            {" · "}
            <strong className="font-medium text-primary-700">{scaffold.short_name}</strong>
          </>
        )}
        {linker && (
          <>
            {" · "}
            <strong className="font-medium text-primary-700">{linker.name}</strong>
          </>
        )}
      </p>

      <Card className="border-accent-200 bg-gradient-to-r from-accent-50 to-white mb-6">
        <CardContent className="p-5">
          <div className="flex items-start gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-accent-100 flex items-center justify-center flex-shrink-0">
              <Bot className="w-5 h-5 text-accent-600" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-primary-900">
                {scaffold
                  ? `Assembled onto ${scaffold.short_name}${linker ? ` with ${linker.name}` : ""}`
                  : "Candidates under this screening"}
              </h3>
              <p className="text-sm text-gray-500 mt-1 leading-relaxed">
                {route.name} · {route.barrier_label} · immunogenicity gate ≤{" "}
                {route.screening.immunogenicity_threshold.toFixed(2)}
                <InfoTip content={GLOSSARY.immunogenicity_gate} className="ml-1 align-middle" />
                {linker && (
                  <>
                    {" · linker "}
                    {linker.length} aa, {linker.rigidity.toLowerCase()}
                  </>
                )}
              </p>
            </div>
          </div>

          {loading && <ListSkeleton rows={3} />}
          {error && <ErrorState error={error} onRetry={reload} compact />}

          {data && counts && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Tally label="Assessed clear" value={counts.clear} tone="ok" note="no gate out of bounds" />
                <Tally
                  label="Threshold band"
                  value={counts.borderline}
                  tone="warn"
                  note="within 10% of a gate"
                />
                <Tally
                  label="Vetoed"
                  value={counts.vetoed}
                  tone="danger"
                  note="a gate was exceeded"
                />
                <Tally
                  label="Indeterminate"
                  value={counts.indeterminate}
                  tone="neutral"
                  note="nothing assessed"
                />
              </div>
              <p className="text-[11px] text-gray-400 mt-3 leading-relaxed">
                Counted over all {counts.ranked} candidate{counts.ranked === 1 ? "" : "s"} the
                selected directions hold, not over the {items.length} shown here, so the figures
                describe the candidate set rather than where this page stopped. The ranking and
                the tally are both computed under {route.name}'s weighting profile.
                {counts.without_composite > 0 &&
                  ` ${counts.without_composite} candidate${
                    counts.without_composite === 1 ? " carries" : "s carry"
                  } no composite under this route, because the direction's pool has too little
                  spread to weight over; ${
                    counts.without_composite === 1 ? "it sits" : "they sit"
                  } at the end of the ranking rather than counting as a zero.`}
              </p>

              {thresholdReport && thresholdSetCount > 0 && (
                <div className="mt-3 rounded-lg border border-gray-200 bg-surface-alt p-3">
                  <p className="text-xs text-gray-600 leading-relaxed">
                    The screening thresholds removed {thresholdRemoved} candidate
                    {thresholdRemoved === 1 ? "" : "s"} before the ranking was cut.
                    {thresholdReport.removed_by_cap > 0 &&
                      ` ${thresholdReport.removed_by_cap} of them by the per-function cap.`}
                  </p>
                  <ul className="mt-2 space-y-1">
                    {thresholdReport.directions.map((outcome) => (
                      <li key={outcome.direction} className="text-[11px] text-gray-500">
                        {outcome.direction}: {outcome.kept} of {outcome.pool} candidate
                        {outcome.pool === 1 ? "" : "s"} kept
                        {outcome.removed_by_threshold > 0 &&
                          `, ${outcome.removed_by_threshold} below the thresholds`}
                        {outcome.removed_by_cap > 0 &&
                          `, ${outcome.removed_by_cap} over the cap`}
                        {outcome.unassessed > 0 &&
                          `, ${outcome.unassessed} the thresholds could not judge`}
                        {outcome.note && `. ${outcome.note}`}
                      </li>
                    ))}
                  </ul>
                  {thresholdReport.directions.some(
                    (outcome) =>
                      outcome.pool > 0 && outcome.kept / outcome.pool < 0.1,
                  ) && (
                    <p className="text-[11px] text-gray-500 mt-2 leading-relaxed">
                      That is a narrow set. Loosening one of the thresholds brings the rest
                      back, and the candidates that fall are often the ones that move together
                      on the same predictor.
                    </p>
                  )}
                </div>
              )}

              <div className="mt-4 pt-3 border-t border-accent-100 flex items-center justify-between gap-3 flex-wrap">
                {recordError ? (
                  <p className="text-xs text-red-600 max-w-md leading-relaxed">{recordError}</p>
                ) : (
                  <p className="text-xs text-gray-500 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-accent-500" />
                    {recorded
                      ? recorded.created
                        ? "Added to the build history"
                        : "Already in the history; its figures were refreshed"
                      : "Recording this build…"}
                    {recorded && (
                      <span className="text-gray-400">
                        · {new Date(recorded.at).toLocaleTimeString(undefined, {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    )}
                  </p>
                )}
                <Button variant="ghost" size="sm" onClick={onOpenHistory}>
                  <History className="w-4 h-4" />
                  View history
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {data && (
        <div className="space-y-2 mb-6">
          <CollapsibleNotice tone="info" title="Where the scaffold assignment came from">
            {data.binding_note}
          </CollapsibleNotice>
          <CollapsibleNotice tone="info" title="Where the linker came from">
            {data.linker_note}
          </CollapsibleNotice>
          <CollapsibleNotice tone="caution" title="What these scores describe">
            {data.scope_note}
          </CollapsibleNotice>
        </div>
      )}

      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium text-primary-900">
          {items.length} of {data?.total ?? 0} candidate{data?.total === 1 ? "" : "s"}
        </p>
        <span className="inline-flex items-center gap-1 text-xs text-gray-400">
          ranked by composite, {route.name} profile
          <InfoTip content={GLOSSARY.composite} />
        </span>
      </div>

      <div className="space-y-2">
        {items.map((item) => {
          const skin = verdictSkin(item.safety_verdict ?? "indeterminate")
          return (
            <Card
              key={item.id}
              className="border-gray-200 hover:border-primary-200 hover:shadow-sm transition-all duration-200"
            >
              <div className="p-4 flex flex-col sm:flex-row sm:items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-sm font-semibold text-primary-900">
                      {item.name}
                    </span>
                    {item.rank !== null && (
                      <Badge variant="outline" className="text-xs">
                        #{item.rank}
                      </Badge>
                    )}
                    <Badge variant="secondary" className="text-[10px]">
                      {item.direction_label}
                    </Badge>
                    {item.status !== "passed" && (
                      <span className="inline-flex items-center gap-1">
                        <Badge variant="warning" className="text-[10px]">
                          {pipelineStatusLabel(item.status)}
                        </Badge>
                        <InfoTip content={GLOSSARY.pipeline_status} />
                      </span>
                    )}
                  </div>

                  {/*
                    The fused sequence is the reason this step exists, so it is what the card
                    shows. A row whose build produced no sequence renders its known parts and
                    names the part it is missing, rather than falling back to the peptide alone
                    and looking like an ordinary list row.
                  */}
                  <div className="bg-surface-alt rounded-md px-2.5 py-2 font-mono text-[11px] break-all leading-relaxed mt-1.5">
                    {item.segments.length > 0 ? (
                      item.segments.map((segment, index) => (
                        <span
                          key={index}
                          style={{
                            color: sequenceColor(segment),
                            fontWeight: sequenceWeight(segment),
                          }}
                        >
                          {segment.available
                            ? segment.sequence
                            : `[${segment.type}: sequence unavailable]`}
                        </span>
                      ))
                    ) : (
                      <span className="text-gray-400">No assembly was returned for this row.</span>
                    )}
                  </div>

                  <div className="flex items-center gap-3 flex-wrap mt-1.5">
                  <div className={cn("flex items-center gap-1.5 text-[11px]", skin.text)}>
                    <span className={cn("w-1.5 h-1.5 rounded-full", skin.dot)} />
                    {skin.label}
                    <InfoTip
                      content={GLOSSARY[VERDICT_GLOSSARY[item.safety_verdict ?? "indeterminate"]]}
                    />
                  </div>
                    <span className="text-[11px] text-gray-400">
                      peptide {item.peptide_length} aa
                      {item.fused_length !== null && (
                        <> · fused {item.fused_length} aa</>
                      )}
                      {item.linker_name && <> · linker {item.linker_name}</>}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-center">
                    <div className="inline-flex items-center justify-center gap-1 text-xs text-gray-400">
                      Composite
                      <InfoTip content={GLOSSARY.composite} />
                    </div>
                    <div className="text-lg font-bold font-mono text-accent-600">
                      {formatScore(item.composite)}
                    </div>
                    <div className="text-[10px] text-gray-400">
                      {item.backbone_binding === "inferred"
                        ? `${item.backbone_name ?? "scaffold"} target`
                        : item.backbone_binding === "verified"
                          ? "stored binding"
                          : "no scaffold"}
                    </div>
                  </div>
                  {/* The record travels with the link so the construct page can offer a way
                      back to the build it belongs to rather than to the whole library. */}
                  <Link
                    to={`/results/${item.id}?route_id=${route.id}${
                      scaffold ? `&scaffold_id=${scaffold.id}` : ""
                    }${linker ? `&linker_id=${linker.id}` : ""}${
                      recorded ? `&from=${encodeURIComponent(recorded.id)}` : ""
                    }`}
                  >
                    <Button variant="ghost" size="sm">
                      <Eye className="w-4 h-4" />
                      Details
                    </Button>
                  </Link>
                </div>
              </div>
            </Card>
          )
        })}
      </div>

      {data && items.length === 0 && (
        <div className="text-center py-16">
          <AlertTriangle className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">
            These directions hold no candidates, so the build has nothing to rank. The bottom
            channel is the negative-control arm and is never ranked here.
          </p>
        </div>
      )}

      <div className="mt-8 text-center">
        <Button variant="outline" onClick={onReset}>
          <FlaskConical className="w-4 h-4" />
          Build Another
        </Button>
      </div>
    </div>
  )
}

function Tally({
  label,
  value,
  tone,
  note,
}: {
  label: string
  value: number
  tone: "ok" | "warn" | "danger" | "neutral"
  note: string
}) {
  const colour =
    tone === "ok"
      ? "text-accent-600"
      : tone === "warn"
        ? "text-amber-600"
        : tone === "danger"
          ? "text-red-500"
          : "text-gray-500"

  return (
    <div className="p-3 rounded-lg bg-white border border-gray-200">
      <p className="text-[11px] text-gray-400 uppercase">{label}</p>
      <p className={cn("text-lg font-bold font-mono mt-0.5", colour)}>{value}</p>
      <p className="text-[10px] text-gray-400 mt-0.5">{note}</p>
    </div>
  )
}
