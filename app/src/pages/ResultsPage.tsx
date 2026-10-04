import { useCallback, useEffect, useRef, useState } from "react"
import { Link, useParams, useSearchParams } from "react-router-dom"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ErrorState } from "@/components/ui/error-state"
import { ListSkeleton } from "@/components/ui/loading-state"
import { Notice } from "@/components/ui/notice"
import { Skeleton } from "@/components/ui/skeleton"
import { AnalysisBlocks, SafetyGateList, ToolScoreGrid } from "@/components/construct-panels"
import {
  ArrowLeft,
  Bot,
  BarChart3,
  ChevronRight,
  Copy,
  Check,
  Dna,
  ExternalLink,
  Layers,
  Link2,
  Loader2,
  MessageSquare,
  Send,
  Wrench,
  X,
} from "lucide-react"
import {
  fetchConstruct,
  fetchConstructScaffolds,
  fetchReference,
  sendChat,
} from "@/api"
import type {
  ChatMessage as ApiChatMessage,
  ConstructDetail,
  LinkerView,
  ReferenceData,
  ScaffoldSummary,
} from "@/api/types"
import { formLabel, materialFormLabels } from "@/lib/derive"
import { formatScore, verdictSkin } from "@/lib/score"
import { analyseSequence } from "@/lib/sequence"
import { useAsync, useAsyncAction } from "@/lib/useAsync"
import { cn } from "@/lib/utils"

/**
 * The construct page.
 *
 * The route travels in the query string rather than in a local default. A composite, a safety
 * verdict and the immunogenicity gate all depend on the application route, so a page that
 * picked one silently would be showing a number whose basis the reader cannot see. Links from
 * the library and the builder carry the route they were screened under.
 *
 * `scaffold_id` is a preview, not a stored fact. When present the response assembles the fused
 * sequence against that scaffold and reports `backbone_binding` as inferred.
 */

type ResultTab = "peptide" | "construct" | "scaffold" | "linker"

const TAB_LABELS: Record<
  ResultTab,
  { name: string; icon: typeof Dna; description: string }
> = {
  peptide: {
    name: "Peptide",
    icon: Dna,
    description: "Peptide origin, sequence features, per-tool scores",
  },
  construct: {
    name: "Construct",
    icon: Wrench,
    description: "Composite scoring, safety gates, sequence composition, expression strategy",
  },
  scaffold: {
    name: "Scaffold",
    icon: Layers,
    description: "Scaffold provenance and the assembly target",
  },
  linker: {
    name: "Linker",
    icon: Link2,
    description: "Linker sequence, rigidity and literature reference",
  },
}

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams, setSearchParams] = useSearchParams()

  const routeId = searchParams.get("route_id")
  const scaffoldId = searchParams.get("scaffold_id")
  const linkerId = searchParams.get("linker_id")

  const [activeTab, setActiveTab] = useState<ResultTab>("construct")
  const [chatOpen, setChatOpen] = useState(false)
  const [bottomChatOpen, setBottomChatOpen] = useState(false)
  const [messages, setMessages] = useState<ApiChatMessage[]>([])
  const [input, setInput] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const load = useCallback(async () => {
    if (!id) throw new Error("No construct identifier in the route.")
    const [reference, detail, candidates] = await Promise.all([
      fetchReference(),
      fetchConstruct(id, { route_id: routeId, scaffold_id: scaffoldId, linker_id: linkerId }),
      fetchConstructScaffolds(id),
    ])
    return { reference, detail, candidates }
  }, [id, routeId, scaffoldId, linkerId])

  const { data, loading, error, reload } = useAsync(load, [id, routeId, scaffoldId, linkerId])

  const chat = useAsyncAction(
    (constructId: string, message: string, route: string | null, history: ApiChatMessage[]) =>
      sendChat(constructId, { message, route_id: route, history }),
  )

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || !id) return

    const outgoing: ApiChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
      actions: [],
    }
    const history = [...messages, outgoing]
    setMessages(history)
    setInput("")

    const response = await chat.run(id, text, routeId, history)
    if (response) setMessages((current) => [...current, response.message])
  }

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 space-y-6">
        <Skeleton className="h-24 w-full" />
        <ListSkeleton rows={2} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center px-4">
        <div className="w-full max-w-2xl">
          <ErrorState error={error} onRetry={reload} />
          <div className="text-center mt-6">
            <Link to="/library">
              <Button variant="outline">
                <ArrowLeft className="w-4 h-4" />
                Back to Library
              </Button>
            </Link>
          </div>
        </div>
      </div>
    )
  }

  if (!data) return null
  const { reference, detail, candidates } = data

  const route = reference.routes.find((item) => item.id === routeId) ?? null
  const activeRouteName = route?.name ?? "the default route"
  const skin = verdictSkin(detail.safety.verdict)
  const labels = materialFormLabels(reference)

  const setScaffoldPreview = (nextId: string | null) => {
    const next = new URLSearchParams(searchParams)
    if (nextId) next.set("scaffold_id", nextId)
    else next.delete("scaffold_id")
    setSearchParams(next, { replace: true })
  }

  const clearLinkerPreview = () => {
    const next = new URLSearchParams(searchParams)
    next.delete("linker_id")
    setSearchParams(next, { replace: true })
  }

  const setRoute = (nextId: string) => {
    const next = new URLSearchParams(searchParams)
    next.set("route_id", nextId)
    setSearchParams(next, { replace: true })
  }

  return (
    <div className="min-h-[calc(100vh-8rem)]">
      <section className="gradient-hero border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Link
            to="/library"
            className="text-sm text-primary-500 hover:text-primary-700 flex items-center gap-1 mb-4 w-fit"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Library
          </Link>

          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <Badge variant="accent">Construct</Badge>
                {detail.rank !== null && <Badge variant="outline">#{detail.rank}</Badge>}
                <Badge variant="outline">{detail.direction_label}</Badge>
                <Badge variant={skin.badge} className="text-xs">
                  {skin.label}
                </Badge>
                {detail.status !== "passed" && (
                  <Badge variant="warning" className="text-xs">
                    Pipeline status {detail.status}
                  </Badge>
                )}
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold text-primary-900 font-mono truncate">
                {detail.name}
              </h1>
              <p className="text-sm text-gray-500 mt-1 flex items-center gap-2 flex-wrap">
                <span>
                  {detail.scaffold?.short_name ?? (
                    <span className="text-amber-600">scaffold unassigned</span>
                  )}
                </span>
                <span className="text-gray-300">|</span>
                <span>{detail.linker?.name ?? "no linker"}</span>
                <span className="text-gray-300">|</span>
                <span className="font-mono text-primary-500 break-all">
                  {detail.peptide.sequence}
                </span>
              </p>
            </div>

            <div className="text-left sm:text-right flex-shrink-0">
              <p className="text-xs text-gray-400">Composite · {activeRouteName}</p>
              <p className="text-5xl font-extrabold gradient-accent-text font-mono leading-none mt-1">
                {formatScore(detail.scores.composite)}
              </p>
              <p className="text-[11px] text-gray-400 mt-1">/ 1.00</p>
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-gray-200 bg-white sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex gap-1 overflow-x-auto">
            {(Object.keys(TAB_LABELS) as ResultTab[]).map((tab) => {
              const Tab = TAB_LABELS[tab]
              const Icon = Tab.icon
              const isActive = activeTab === tab
              return (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "flex items-center gap-2.5 px-5 py-3.5 border-b-2 transition-all duration-200 whitespace-nowrap cursor-pointer",
                    isActive
                      ? "border-primary-500 text-primary-700"
                      : "border-transparent text-gray-500 hover:text-primary-600 hover:border-gray-300",
                  )}
                >
                  <Icon className={cn("w-4 h-4", isActive ? "text-primary-600" : "text-gray-400")} />
                  <span className="font-semibold text-sm">{Tab.name}</span>
                </button>
              )
            })}
          </div>
          <p className="text-xs text-gray-400 py-2">{TAB_LABELS[activeTab].description}</p>
        </div>
      </section>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {activeTab === "peptide" && <PeptideTab detail={detail} />}
            {activeTab === "construct" && (
              <ConstructTab
                detail={detail}
                reference={reference}
                activeRouteId={routeId}
                activeRouteName={activeRouteName}
                onSelectRoute={setRoute}
              />
            )}
            {activeTab === "scaffold" && (
              <ScaffoldTab
                detail={detail}
                candidates={candidates}
                labels={labels}
                onPreview={setScaffoldPreview}
              />
            )}
            {activeTab === "linker" && (
              <LinkerTab
                linker={detail.linker}
                note={detail.linker_note}
                previewing={Boolean(linkerId)}
                onClear={clearLinkerPreview}
              />
            )}

            <ChatBar
              open={bottomChatOpen}
              messages={messages}
              input={input}
              pending={chat.pending}
              error={chat.error?.message ?? null}
              onInput={setInput}
              onOpen={() => setBottomChatOpen(true)}
              onSend={handleSend}
              placeholder={`Ask about ${detail.name} — scoring, gates, expression strategy…`}
            />
          </div>

          <div className="space-y-4">
            {!chatOpen && (
              <Button
                variant="gradient"
                className="w-full"
                size="lg"
                onClick={() => setChatOpen(true)}
              >
                <Bot className="w-5 h-5" />
                Open AI Sidebar
                <MessageSquare className="w-4 h-4" />
              </Button>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5">
                <StatRow
                  label={`Composite · ${activeRouteName}`}
                  value={formatScore(detail.scores.composite)}
                  highlight
                />
                <StatRow label="Rank" value={detail.rank !== null ? `#${detail.rank}` : "—"} />
                <StatRow label="Function" value={detail.direction_label} />
                <StatRow
                  label="Scaffold"
                  value={detail.scaffold?.short_name ?? "unassigned"}
                  tone={detail.scaffold ? undefined : "danger"}
                />
                <StatRow
                  label="Binding"
                  value={detail.backbone_binding}
                  tone={detail.backbone_binding === "placeholder" ? "danger" : "ok"}
                />
                <StatRow label="Linker" value={detail.linker?.name ?? "—"} />
                <StatRow label="Safety gates" value={skin.label} tone={skin.dot === "bg-accent-500" ? "ok" : "danger"} />

                <div className="pt-2 border-t border-gray-100">
                  <p className="text-xs text-gray-400 mb-1">Screened under</p>
                  <select
                    value={routeId ?? route?.id ?? ""}
                    onChange={(event) => setRoute(event.target.value)}
                    className="w-full h-9 rounded-lg border border-gray-200 bg-white px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary-400"
                  >
                    {reference.routes.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} · immuno ≤ {item.screening.immunogenicity_threshold.toFixed(2)}
                      </option>
                    ))}
                  </select>
                </div>

                {detail.peptide.source && (
                  <div className="pt-2 border-t border-gray-100">
                    <p className="text-xs text-gray-400 mb-1">Peptide source</p>
                    <p className="text-xs text-gray-700">{detail.peptide.source}</p>
                  </div>
                )}
                {detail.peptide.source_accession && (
                  <div className="pt-2 border-t border-gray-100">
                    <p className="text-xs text-gray-400 mb-1">Accession</p>
                    <p className="text-xs text-gray-600 break-words">
                      {detail.peptide.source_accession}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {chatOpen && (
        <div className="fixed inset-y-0 right-0 z-30 w-full sm:w-96 lg:w-[420px] bg-white border-l border-gray-200 shadow-2xl flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg gradient-accent flex items-center justify-center">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-primary-900">PeptiCraft Agent</h3>
                <p className="text-xs text-gray-400">
                  {chat.data?.llm_configured === false || chat.data === null
                    ? "Template answers from this construct's record"
                    : "Experiment decision support"}
                </p>
              </div>
            </div>
            <button
              onClick={() => setChatOpen(false)}
              className="p-1.5 rounded-lg hover:bg-surface-alt transition-colors text-gray-400 hover:text-gray-600 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="px-4 py-2 border-b border-gray-100 bg-surface-alt">
            <div className="flex items-center gap-2 text-xs text-gray-500 flex-wrap">
              <span className="font-mono text-primary-500">{detail.name}</span>
              <span>·</span>
              <span>Composite {formatScore(detail.scores.composite)}</span>
              <span>·</span>
              <span>{activeRouteName}</span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {messages.length === 0 && (
              <div className="text-xs text-gray-400 leading-relaxed">
                Answers are derived from this construct's own record. The service is stateless and
                idempotent, so the same question under the same route always returns the same
                text. The immunogenicity gate and the composite change with the route, so the same
                question can have a different correct answer under another one.
              </div>
            )}
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {chat.pending && <ThinkingBubble />}
            {chat.error && <ErrorState error={chat.error} compact />}
            {chat.data && chat.data.suggested_questions.length > 0 && (
              <div className="space-y-1.5">
                {chat.data.suggested_questions.map((question) => (
                  <button
                    key={question}
                    onClick={() => setInput(question)}
                    className="block w-full text-left text-xs text-primary-600 hover:text-primary-800 rounded-lg border border-gray-200 hover:border-primary-200 px-3 py-2 transition-colors cursor-pointer"
                  >
                    {question}
                  </button>
                ))}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="px-4 py-3 border-t border-gray-200">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && handleSend()}
                placeholder="Ask about this construct…"
                className="flex-1 h-10 rounded-lg border border-gray-300 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
              />
              <Button
                variant="gradient"
                size="icon"
                onClick={handleSend}
                disabled={!input.trim() || chat.pending}
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      )}

      {chatOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-20 sm:hidden"
          onClick={() => setChatOpen(false)}
        />
      )}
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════════
// Tab 1 — peptide
// ════════════════════════════════════════════════════════════════════════════

function PeptideTab({ detail }: { detail: ConstructDetail }) {
  const features = analyseSequence(detail.peptide.sequence)
  const { supplementary } = detail

  const supplementaryRows: { label: string; value: number | null; note: string }[] = [
    {
      label: "MHC-II percent rank (NetMHCIIpan)",
      value: supplementary.immunogenicity_ii_pct_rank,
      note: "0–100, lower is a stronger binder. A percent rank, not a probability.",
    },
    {
      label: "Allergenicity (AlgPred2)",
      value: supplementary.allergenicity,
      note: "Soft signal; not a veto gate.",
    },
    {
      label: "Aggregation propensity (AGGRESCAN A3v)",
      value: supplementary.aggregation_a3v,
      note: "One-dimensional AGGRESCAN, computed at assembly time. Lower is better.",
    },
    {
      label: "Free-radical scavenging (AnOxPePred)",
      value: supplementary.anoxpepred_frs,
      note: "The head that ranks the antioxidant direction.",
    },
    {
      label: "Metal chelation (AnOxPePred)",
      value: supplementary.anoxpepred_chel,
      note: "The predictor's second head.",
    },
    {
      label: "Antioxidant SVM (AOPxSVM)",
      value: supplementary.aopxsvm,
      note: "Stored as a class index; the probability lives in the tool's own details.",
    },
    {
      label: "Antibacterial (AMPlify v0.1.0)",
      value: supplementary.amp_esm,
      note: "Ranked the antibacterial direction before the iMFP-LG channel took over.",
    },
    {
      label: "Antibacterial (iMFP-LG AMP channel)",
      value: supplementary.imfp_lg_amp,
      note: "The AMP channel of the multi-label model.",
    },
    {
      label: "Anti-inflammatory (iMFP-LG AIP channel)",
      value: supplementary.imfp_lg_aip,
      note: "Ranking signal: the model separates functional-looking peptides from random fragments.",
    },
    {
      label: "Tyrosinase inhibition (TIPred)",
      value: supplementary.tipred,
      note: "Ranks the anti-melanin direction.",
    },
  ]

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Dna className="w-5 h-5 text-primary-500" />
            Functional Peptide
          </CardTitle>
          <CardDescription>Sequence, provenance and the biophysical features it implies.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="rounded-lg border border-gray-200 bg-surface-alt p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-gray-400 uppercase tracking-wide">Sequence</p>
              <span className="text-xs text-gray-400 font-mono">
                {detail.peptide.length} aa
              </span>
            </div>
            <p className="font-mono text-base text-primary-700 break-all leading-relaxed">
              {detail.peptide.sequence}
            </p>
          </div>

          <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-gray-500">
            <span>
              <span className="text-gray-400">MW</span>{" "}
              {features.molecularWeight.toFixed(0)} Da
            </span>
            <span>
              <span className="text-gray-400">Net charge</span>{" "}
              {features.netCharge > 0 ? "+" : ""}
              {features.netCharge}
            </span>
            <span>
              <span className="text-gray-400">Cys</span> {features.cysCount}
            </span>
            <span>
              <span className="text-gray-400">Aromatic</span> {features.aromaticPct}%
            </span>
            <span>
              <span className="text-gray-400">Hydrophobic</span> {features.hydrophobicPct}%
            </span>
            <span>
              <span className="text-gray-400">Gly</span> {features.glycinePct}%
            </span>
            <span>
              <span className="text-gray-400">Pro</span> {features.prolinePct}%
            </span>
          </div>

          <dl className="grid sm:grid-cols-2 gap-x-6 gap-y-3 text-sm border-t border-gray-100 pt-4">
            <InfoRow label="Source" value={detail.peptide.source} />
            <InfoRow label="Source version" value={detail.peptide.source_version} />
            <InfoRow
              label="Source accession"
              value={detail.peptide.source_accession ?? "not recorded"}
              span
            />
            <InfoRow label="Sequence MD5" value={detail.peptide.seq_md5} span mono />
            <InfoRow label="Database peptide id" value={String(detail.peptide.id)} />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-accent-500" />
            Per-Tool Scores
          </CardTitle>
          <CardDescription>
            The nine reported scores, each with the predictor behind it, the threshold applied
            and whether it was assessed at all.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ToolScoreGrid scores={detail.scores} scoreMeta={detail.score_meta} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Supplementary measurements</CardTitle>
          <CardDescription>
            Real values that have no place in the nine-score grid. Several are the ranking signal
            for a direction the construct does not belong to, which is why they are carried beside
            the grid rather than inside it.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="divide-y divide-gray-100">
            {supplementaryRows.map((row) => (
              <div key={row.label} className="flex items-start justify-between gap-4 py-2.5">
                <div className="min-w-0">
                  <p className="text-xs font-medium text-primary-900">{row.label}</p>
                  <p className="text-[11px] text-gray-400 leading-snug mt-0.5">{row.note}</p>
                </div>
                <span
                  className={cn(
                    "font-mono text-sm flex-shrink-0",
                    row.value === null ? "text-gray-300" : "text-primary-800",
                  )}
                >
                  {formatScore(row.value, 3)}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </>
  )
}

// ════════════════════════════════════════════════════════════════════════════
// Tab 2 — construct
// ════════════════════════════════════════════════════════════════════════════

function ConstructTab({
  detail,
  reference,
  activeRouteId,
  activeRouteName,
  onSelectRoute,
}: {
  detail: ConstructDetail
  reference: ReferenceData
  activeRouteId: string | null
  activeRouteName: string
  onSelectRoute: (routeId: string) => void
}) {
  const [copied, setCopied] = useState(false)
  const aggregation = detail.supplementary.aggregation_a3v

  const copySequence = () => {
    if (!detail.full_sequence) return
    void navigator.clipboard.writeText(detail.full_sequence)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className="w-5 h-5 text-primary-500" />
            Construct Overview
          </CardTitle>
          <CardDescription>
            Composite under the {activeRouteName} profile, the rank in the stored library, and the
            aggregation propensity the pipeline computes at assembly.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <ScoreTile
              label="Composite"
              value={formatScore(detail.scores.composite)}
              tone={
                detail.scores.composite === null
                  ? "neutral"
                  : detail.scores.composite >= 0.8
                    ? "ok"
                    : detail.scores.composite >= 0.6
                      ? "warn"
                      : "danger"
              }
              footnote={activeRouteName}
            />
            <ScoreTile
              label="Rank"
              value={detail.rank !== null ? `#${detail.rank}` : "—"}
              tone="neutral"
              footnote="stored library order"
            />
            <ScoreTile
              label="Aggregation A3v"
              value={formatScore(aggregation)}
              tone={aggregation === null ? "neutral" : aggregation < 0 ? "ok" : "warn"}
              footnote={
                aggregation === null
                  ? "not computed"
                  : "mean per-residue AGGRESCAN score; negative is aggregation-averse"
              }
            />
          </div>

          <SafetyGateList safety={detail.safety} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Sequence Composition</CardTitle>
              <CardDescription>
                Assembled as backbone + linker + peptide. A segment whose sequence is unknown is
                shown by label without residues.
              </CardDescription>
            </div>
            {detail.assembled_sequence_available && (
              <Button
                variant="ghost"
                size="icon"
                onClick={copySequence}
                className="text-gray-400 hover:text-primary-600 flex-shrink-0"
              >
                {copied ? (
                  <Check className="w-4 h-4 text-accent-500" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-3">
            {detail.segments.map((segment, index) => (
              <div key={index} className="flex items-center gap-1.5 text-xs">
                <div
                  className={cn(
                    "w-3 h-3 rounded-sm",
                    !segment.available && "opacity-30",
                  )}
                  style={{ backgroundColor: segment.color }}
                />
                <span className="text-gray-500">{segment.label}</span>
                <span className="text-gray-400">({segment.sequence.length} aa)</span>
              </div>
            ))}
          </div>

          <div className="bg-surface-alt rounded-lg p-4 font-mono text-xs break-all leading-relaxed max-h-48 overflow-y-auto">
            {detail.segments.map((segment, index) => (
              <span
                key={index}
                style={{
                  color: segment.available ? segment.color : "#9ca3af",
                  fontWeight: segment.type === "peptide" ? 600 : 400,
                }}
              >
                {segment.available ? segment.sequence : `[${segment.type}: sequence unavailable]`}
              </span>
            ))}
          </div>

          {!detail.assembled_sequence_available && (
            <Notice tone="caution" title="No fused sequence is available">
              {detail.backbone_binding_note}
            </Notice>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Composite by application route</CardTitle>
          <CardDescription>
            The same construct under each route's weighting profile. Immunogenicity is a property
            of the peptide and does not move between routes; penetration, solubility, thermal
            stability and the composite all do.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-200">
                  <th className="py-2 pr-3 font-medium">Route</th>
                  <th className="py-2 pr-3 font-medium text-right">Penetration</th>
                  <th className="py-2 pr-3 font-medium text-right">Solubility</th>
                  <th className="py-2 pr-3 font-medium text-right">Thermal</th>
                  <th className="py-2 pr-3 font-medium text-right">Composite</th>
                  <th className="py-2 font-medium text-right">Immuno gate</th>
                </tr>
              </thead>
              <tbody>
                {reference.routes.map((item) => {
                  const scores = detail.delivery_scores[item.id]
                  const isActive = item.id === activeRouteId
                  return (
                    <tr
                      key={item.id}
                      className={cn(
                        "border-b border-gray-100 last:border-0 cursor-pointer hover:bg-surface-alt/60",
                        isActive && "bg-primary-50/60",
                      )}
                      onClick={() => onSelectRoute(item.id)}
                    >
                      <td className="py-2 pr-3">
                        <span
                          className={cn(
                            "font-medium",
                            isActive ? "text-primary-800" : "text-gray-700",
                          )}
                        >
                          {item.name}
                        </span>
                        {isActive && (
                          <Badge variant="accent" className="text-[9px] ml-1.5">
                            showing
                          </Badge>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono text-gray-600">
                        {formatScore(scores?.cpp ?? null)}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono text-gray-600">
                        {formatScore(scores?.solubility ?? null)}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono text-gray-600">
                        {formatScore(scores?.thermal_stability ?? null)}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono font-semibold text-primary-800">
                        {formatScore(scores?.composite ?? null)}
                      </td>
                      <td className="py-2 text-right font-mono text-gray-600">
                        {item.screening.immunogenicity_threshold.toFixed(2)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-gray-400 mt-3 leading-relaxed">
            Select a row to recompute the page under that route. The immunogenicity gate applied to
            this construct is the one in the last column of the selected row.
          </p>
        </CardContent>
      </Card>

      <AnalysisBlocks constructId={detail.id} routeId={activeRouteId} />
    </>
  )
}

// ════════════════════════════════════════════════════════════════════════════
// Tab 3 — scaffold
// ════════════════════════════════════════════════════════════════════════════

function ScaffoldTab({
  detail,
  candidates,
  labels,
  onPreview,
}: {
  detail: ConstructDetail
  candidates: ScaffoldSummary[]
  labels: Record<string, string>
  onPreview: (scaffoldId: string | null) => void
}) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-primary-500" />
            Scaffold binding
          </CardTitle>
          <CardDescription>
            Where the scaffold in this construct came from, and what that means for the fused
            sequence.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Notice
            tone={detail.backbone_binding === "placeholder" ? "caution" : "info"}
            title={
              detail.backbone_binding === "placeholder"
                ? "The stored binding is a placeholder"
                : detail.backbone_binding === "verified"
                  ? "The stored binding carries a real scaffold"
                  : "The scaffold was named at request time"
            }
          >
            {detail.backbone_binding_note}
          </Notice>

          {detail.scaffold && (
            <div className="rounded-lg border border-gray-200 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-primary-900">
                      {detail.scaffold.short_name}
                    </span>
                    {detail.scaffold.length !== null && (
                      <Badge variant="secondary" className="text-xs">
                        {detail.scaffold.length} aa
                      </Badge>
                    )}
                    {detail.scaffold.max_evidence && (
                      <Badge variant="accent" className="text-xs">
                        Evidence {detail.scaffold.max_evidence}
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-1">{detail.scaffold.applicant}</p>
                  {detail.scaffold.species && (
                    <p className="text-xs text-gray-500 mt-1 italic">{detail.scaffold.species}</p>
                  )}
                  {detail.scaffold.material_forms.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {detail.scaffold.material_forms.map((form) => (
                        <Badge key={form} variant="outline" className="text-[10px]">
                          {formLabel(labels, form)}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
                <Link to={`/library/scaffold/${detail.scaffold.id}`} className="flex-shrink-0">
                  <Button variant="ghost" size="sm">
                    <ExternalLink className="w-3.5 h-3.5" />
                    Full page
                  </Button>
                </Link>
              </div>

              <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between gap-3">
                <p className="text-[11px] text-gray-400">
                  This preview is not stored. Clear it to return to the record as it stands.
                </p>
                <Button variant="outline" size="sm" onClick={() => onPreview(null)}>
                  Clear preview
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Eligible scaffolds</CardTitle>
          <CardDescription>
            Scaffolds the patent dataset tags for this construct's application routes. Selecting one
            assembles the fused sequence against it and reports the binding as inferred. The service
            never applies a scaffold silently.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {candidates.map((scaffold) => (
            <button
              key={scaffold.id}
              onClick={() => onPreview(scaffold.id)}
              disabled={!scaffold.has_sequence}
              className={cn(
                "w-full text-left p-3 rounded-lg border transition-all duration-200",
                detail.scaffold?.id === scaffold.id
                  ? "border-primary-400 bg-primary-50"
                  : scaffold.has_sequence
                    ? "border-gray-200 hover:border-primary-200 hover:bg-surface-alt cursor-pointer"
                    : "border-dashed border-gray-200 opacity-60 cursor-not-allowed",
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-primary-900">
                      {scaffold.short_name}
                    </span>
                    {scaffold.max_evidence && (
                      <Badge variant="outline" className="text-[10px]">
                        {scaffold.max_evidence}
                      </Badge>
                    )}
                    {!scaffold.has_sequence && (
                      <Badge variant="warning" className="text-[10px]">
                        no sequence
                      </Badge>
                    )}
                  </div>
                  <p className="text-[11px] text-gray-400 mt-0.5">{scaffold.applicant}</p>
                </div>
                {scaffold.has_sequence && (
                  <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0" />
                )}
              </div>
            </button>
          ))}

          {candidates.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-6">
              No scaffold in the library is tagged for this construct's application routes.
            </p>
          )}
        </CardContent>
      </Card>
    </>
  )
}

// ════════════════════════════════════════════════════════════════════════════
// Tab 4 — linker
// ════════════════════════════════════════════════════════════════════════════

function LinkerTab({
  linker,
  note,
  previewing,
  onClear,
}: {
  linker: LinkerView | null
  note: string
  previewing: boolean
  onClear: () => void
}) {
  if (!linker) {
    return (
      <Card>
        <CardContent className="p-6">
          <p className="text-sm text-gray-500">
            This construct carries no linker reference.
          </p>
        </CardContent>
      </Card>
    )
  }

  const fromSampleTable = linker.source_table === "linkers"

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Link2 className="w-5 h-5 text-primary-500" />
          {linker.name}
        </CardTitle>
        <CardDescription>
          {linker.rigidity} · {linker.length} aa · read from <code>{linker.source_table}</code>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Two separate questions, so two separate notices: who named this linker, and which
            table it came out of. A linker named at request time can come from either table. */}
        {previewing && (
          <Notice tone="info" title="This linker was named at request time">
            {note}
          </Notice>
        )}

        {fromSampleTable && (
          <Notice tone="caution" title="This linker comes from the sample table">
            The assembly script that wrote these constructs took the first available row of the
            six-row sample table, so the recorded linker was not chosen for this construct. The
            curated fifteen-entry library is what the Builder offers instead.
          </Notice>
        )}

        <div className="rounded-lg border border-gray-200 bg-gradient-to-br from-primary-50/60 via-white to-accent-50/40 px-4 py-5">
          <p className="font-mono text-center text-base font-semibold text-primary-700 break-all tracking-wide">
            {linker.sequence}
          </p>
        </div>

        {linker.description && (
          <p className="text-sm text-gray-600 leading-relaxed">{linker.description}</p>
        )}

        {linker.unit_composition.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Composition
            </p>
            <div className="space-y-1.5">
              {linker.unit_composition.map((unit, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-surface-alt border border-gray-100"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-primary-900 font-medium">
                      {unit.unit}
                    </span>
                    <span className="text-xs text-gray-500">— {unit.label}</span>
                  </div>
                  <span className="text-xs font-mono text-primary-700 font-semibold">
                    ×{unit.count}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {linker.reference && (
          <div className="pt-3 border-t border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Reference
            </p>
            <p className="text-xs text-gray-600 italic leading-relaxed">{linker.reference}</p>
          </div>
        )}

        {previewing && (
          <div className="pt-3 border-t border-gray-100 flex items-center justify-between gap-3">
            <p className="text-[11px] text-gray-400">
              This preview is not stored. Clear it to return to the record as it stands.
            </p>
            <Button variant="outline" size="sm" onClick={onClear}>
              Clear preview
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ════════════════════════════════════════════════════════════════════════════
// Chat
// ════════════════════════════════════════════════════════════════════════════

function ChatBar({
  open,
  messages,
  input,
  pending,
  error,
  onInput,
  onOpen,
  onSend,
  placeholder,
}: {
  open: boolean
  messages: ApiChatMessage[]
  input: string
  pending: boolean
  error: string | null
  onInput: (value: string) => void
  onOpen: () => void
  onSend: () => void
  placeholder: string
}) {
  return (
    <div className="border border-accent-200 bg-gradient-to-r from-accent-50 to-white rounded-xl p-4">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg gradient-accent flex items-center justify-center flex-shrink-0">
          <Bot className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <input
            type="text"
            value={input}
            onChange={(event) => onInput(event.target.value)}
            onFocus={onOpen}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                onOpen()
                onSend()
              }
            }}
            placeholder={placeholder}
            className="w-full h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent-400 focus:border-transparent transition-all"
          />
        </div>
        <Button
          variant="gradient"
          size="icon"
          onClick={() => {
            onOpen()
            onSend()
          }}
          disabled={!input.trim() || pending}
        >
          {pending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </Button>
      </div>

      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}

      {open && messages.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100 max-h-80 overflow-y-auto space-y-3">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} compact />
          ))}
          {pending && <ThinkingBubble compact />}
        </div>
      )}
    </div>
  )
}

function MessageBubble({
  message,
  compact,
}: {
  message: ApiChatMessage
  compact?: boolean
}) {
  const isUser = message.role === "user"
  return (
    <div className={cn("flex gap-2", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div
          className={cn(
            "rounded-full gradient-accent flex items-center justify-center flex-shrink-0",
            compact ? "w-6 h-6" : "w-7 h-7 mt-1",
          )}
        >
          <Bot className={compact ? "w-3 h-3 text-white" : "w-3.5 h-3.5 text-white"} />
        </div>
      )}
      <div
        className={cn(
          "max-w-[85%] rounded-xl px-3 py-2 leading-relaxed whitespace-pre-line",
          compact ? "text-xs" : "text-sm",
          isUser
            ? "bg-primary-500 text-white rounded-br-sm"
            : "bg-surface-alt text-primary-800 rounded-bl-sm",
        )}
      >
        {message.content}
      </div>
    </div>
  )
}

function ThinkingBubble({ compact }: { compact?: boolean }) {
  return (
    <div className="flex gap-2">
      <div
        className={cn(
          "rounded-full gradient-accent flex items-center justify-center flex-shrink-0",
          compact ? "w-6 h-6" : "w-7 h-7",
        )}
      >
        <Bot className={compact ? "w-3 h-3 text-white" : "w-3.5 h-3.5 text-white"} />
      </div>
      <div className="bg-surface-alt rounded-xl px-3 py-2 flex gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-accent-400 animate-bounce" />
        <span
          className="w-1.5 h-1.5 rounded-full bg-accent-400 animate-bounce"
          style={{ animationDelay: "150ms" }}
        />
        <span
          className="w-1.5 h-1.5 rounded-full bg-accent-400 animate-bounce"
          style={{ animationDelay: "300ms" }}
        />
      </div>
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════════
// Small components
// ════════════════════════════════════════════════════════════════════════════

function ScoreTile({
  label,
  value,
  tone,
  footnote,
}: {
  label: string
  value: string
  tone: "ok" | "warn" | "danger" | "neutral"
  footnote: string
}) {
  const colour =
    tone === "ok"
      ? "text-accent-700"
      : tone === "warn"
        ? "text-amber-700"
        : tone === "danger"
          ? "text-red-700"
          : "text-primary-700"

  return (
    <div className="p-4 rounded-lg border border-gray-200 bg-white">
      <p className="text-xs text-gray-400 uppercase tracking-wide">{label}</p>
      <p className={cn("text-2xl font-bold font-mono mt-1", colour)}>{value}</p>
      <p className="text-[11px] text-gray-400 mt-0.5">{footnote}</p>
    </div>
  )
}

function StatRow({
  label,
  value,
  highlight,
  tone,
}: {
  label: string
  value: string
  highlight?: boolean
  tone?: "ok" | "danger"
}) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-gray-500 flex-shrink-0">{label}</span>
      <span
        className={cn(
          "font-medium font-mono text-xs text-right break-words",
          tone === "ok"
            ? "text-accent-600"
            : tone === "danger"
              ? "text-amber-600"
              : highlight
                ? "text-accent-600 font-bold text-base"
                : "text-primary-900",
        )}
      >
        {value}
      </span>
    </div>
  )
}

function InfoRow({
  label,
  value,
  span,
  mono,
}: {
  label: string
  value: string
  span?: boolean
  mono?: boolean
}) {
  return (
    <div className={span ? "sm:col-span-2" : ""}>
      <dt className="text-xs text-gray-400 mb-1">{label}</dt>
      <dd className={cn("text-sm text-gray-700 leading-relaxed break-words", mono && "font-mono text-xs")}>
        {value}
      </dd>
    </div>
  )
}
