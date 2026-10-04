import { useCallback, useState } from "react"
import { ChevronDown, Loader2, Sparkles } from "lucide-react"

import { fetchConstructAnalysis } from "@/api"
import type {
  AnalysisBlock,
  ConstructDetail,
  ConstructScores,
  SafetyVerdict,
  ScoreMeta,
} from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { RankingOnlyMarker } from "@/components/ui/notice"
import { Skeleton } from "@/components/ui/skeleton"
import {
  SCORE_GROUP_HINT,
  SCORE_GROUP_LABEL,
  thresholdSourceLabel,
} from "@/lib/display"
import {
  barWidth,
  formatScore,
  gateLabeller,
  gateWidth,
  joinNames,
  judgeScore,
  verdictBarColour,
  verdictSkin,
  vetoSummary,
  type ScoreVerdict,
} from "@/lib/score"
import { useAsync, useAsyncAction } from "@/lib/useAsync"
import { cn } from "@/lib/utils"

/**
 * Panels shared by the library row and the results page.
 *
 * Both surfaces show the same three things about a construct — its gates, its per-tool scores,
 * and its generated analysis — so they are defined once here. Two copies would be the same
 * kind of duplicate that let the safety thresholds drift apart in the previous interface.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Safety gates
// ─────────────────────────────────────────────────────────────────────────────

export function SafetyGateList({ safety }: { safety: SafetyVerdict }) {
  const skin = verdictSkin(safety.verdict)

  return (
    <div>
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Safety gates</p>
        <Badge variant={skin.badge} className="text-[10px]">
          {skin.label}
        </Badge>
        {safety.route_id && safety.immunogenicity_threshold !== null && (
          <span className="text-[10px] text-gray-400">
            immunogenicity gate {formatScore(safety.immunogenicity_threshold)} from this route's
            profile
          </span>
        )}
      </div>

      {safety.verdict === "vetoed" && (
        <p className="text-[11px] text-red-600 mb-2">{vetoSummary(safety)}.</p>
      )}

      <div className="grid sm:grid-cols-2 gap-2">
        {safety.gates.map((gate) => {
          const unassessed = gate.passed === null
          const failed = gate.passed === false
          const watched = gate.passed === true && gate.borderline
          const width = gateWidth(gate.value, gate.threshold, gate.higher_is_better)

          return (
            <div key={gate.key} className="rounded-lg border border-gray-200 bg-white p-2.5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs font-semibold text-primary-900">{gate.label}</span>
                    {gate.threshold_source === "route" && (
                      <Badge variant="outline" className="text-[9px]">
                        route gate
                      </Badge>
                    )}
                    {!gate.is_veto_gate && (
                      <Badge variant="secondary" className="text-[9px]">
                        soft signal
                      </Badge>
                    )}
                  </div>
                  <p className="font-mono text-[11px] text-gray-400 mt-0.5">{gate.tool}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <div
                    className={cn(
                      "font-mono text-sm font-bold",
                      unassessed
                        ? "text-gray-300"
                        : failed
                          ? "text-red-600"
                          : watched
                            ? "text-amber-600"
                            : "text-accent-600",
                    )}
                  >
                    {formatScore(gate.value)}
                  </div>
                  <div className="text-[10px] text-gray-400">
                    {unassessed
                      ? "not assessed"
                      : `${gate.higher_is_better ? "at least" : "at most"} ${formatScore(
                          gate.threshold,
                        )}`}
                  </div>
                </div>
              </div>

              {!unassessed && (
                <div className="h-1.5 rounded-full bg-surface-muted mt-2 overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      failed ? "bg-red-400" : watched ? "bg-amber-400" : "bg-accent-500",
                    )}
                    style={{ width }}
                  />
                </div>
              )}

              {gate.note && (
                <p className="text-[10px] text-gray-400 mt-1.5 leading-snug">{gate.note}</p>
              )}
            </div>
          )
        })}
      </div>

      {safety.unassessed.length > 0 && (
        <p className="text-[11px] text-gray-400 mt-2 leading-relaxed">
          Not assessed: {joinNames(safety.unassessed.map(gateLabeller(safety.gates)))}. An
          unassessed metric does not eliminate a candidate — the pipeline's null-passthrough
          rule is that a score removes a candidate only when it is present and out of bounds.
        </p>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Per-tool score grid
// ─────────────────────────────────────────────────────────────────────────────

export function ToolScoreGrid({
  scores,
  scoreMeta,
  columns = 2,
}: {
  scores: ConstructScores
  scoreMeta: Record<string, ScoreMeta>
  columns?: 1 | 2
}) {
  const groups = ["function", "safety", "developability"] as const
  const entries = Object.entries(scoreMeta)
  const values = scores as unknown as Record<string, number | null>

  return (
    <div className="space-y-4">
      {groups.map((group) => {
        const inGroup = entries.filter(([, meta]) => meta.group === group)
        if (inGroup.length === 0) return null

        return (
          <div key={group}>
            <p
              className={cn(
                "text-[11px] font-semibold mb-2 uppercase tracking-wide",
                group === "safety" ? "text-red-500" : "text-primary-600",
              )}
            >
              {SCORE_GROUP_LABEL[group]}
              <span className="ml-2 font-normal normal-case tracking-normal text-gray-400">
                {SCORE_GROUP_HINT[group]}
              </span>
            </p>
            <div className={cn("grid gap-2", columns === 2 ? "sm:grid-cols-2" : "")}>
              {inGroup.map(([key, meta]) => {
                const value = values[key] ?? null
                const verdict = judgeScore(meta, value)
                return (
                  <ScoreCard key={key} meta={meta} value={value} verdict={verdict} />
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ScoreCard({
  meta,
  value,
  verdict,
}: {
  meta: ScoreMeta
  value: number | null
  verdict: ScoreVerdict
}) {
  return (
    <div className="flex items-start gap-2.5 p-3 rounded-lg bg-white border border-gray-200">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-mono text-xs font-semibold text-primary-900">{meta.tool}</span>
          {verdict && (
            <Badge
              variant={
                verdict === "PASS" ? "accent" : verdict === "FAIL" ? "destructive" : "warning"
              }
              className="text-[10px] px-1 py-0"
            >
              {verdict}
            </Badge>
          )}
          {meta.is_veto_gate && (
            <Badge variant="outline" className="text-[9px] px-1 py-0">
              gate
            </Badge>
          )}
          {meta.semantics === "ranking_only" && <RankingOnlyMarker />}
        </div>

        <p className="text-[11px] text-gray-400 leading-snug mt-0.5">{meta.measures}</p>

        {meta.applied_threshold ? (
          <p className="text-[10px] text-gray-400 mt-0.5">
            {meta.higher_is_better ? "at least" : "at most"}{" "}
            {formatScore(meta.applied_threshold.value)},{" "}
            {thresholdSourceLabel(meta.applied_threshold.source)}
          </p>
        ) : (
          <p className="text-[10px] text-gray-400 mt-0.5">
            {meta.higher_is_better ? "higher is better" : "lower is better"}
          </p>
        )}
      </div>

      <div className="text-right flex-shrink-0">
        <div
          className={cn(
            "font-mono text-sm font-bold",
            verdict === "FAIL"
              ? "text-red-600"
              : verdict === "WATCH"
                ? "text-amber-600"
                : value === null
                  ? "text-gray-300"
                  : "text-primary-700",
          )}
        >
          {formatScore(value)}
        </div>
        <div className="w-14 h-1 rounded-full bg-surface-muted mt-1 overflow-hidden">
          <div
            className={cn("h-full rounded-full", verdictBarColour(verdict))}
            style={{ width: barWidth(value) }}
          />
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Generated analysis
// ─────────────────────────────────────────────────────────────────────────────

/**
 * The six analysis blocks, fetched from the service.
 *
 * The text is generated per construct from its own scores, thresholds and route profile, so
 * it is fetched rather than computed here. `provider` is displayed because the current
 * generator is a deterministic template and the surface should not present that as model
 * output.
 */
export function AnalysisBlocks({
  constructId,
  routeId,
}: {
  constructId: string
  routeId: string | null
}) {
  const [blocks, setBlocks] = useState<AnalysisBlock[] | null>(null)
  const [provider, setProvider] = useState("")

  const load = useCallback(
    () => fetchConstructAnalysis(constructId, routeId),
    [constructId, routeId],
  )

  const automatic = useAsync(load, [load])
  const manual = useAsyncAction(load)

  const resolved = blocks ?? automatic.data?.blocks ?? null
  const resolvedProvider = provider || automatic.data?.provider || ""
  const error = manual.error ?? automatic.error

  const generate = async () => {
    const response = await manual.run()
    if (response) {
      setBlocks(response.blocks)
      setProvider(response.provider)
    }
  }

  // A manually generated set replaces the automatic one, so retrying after a failure has to
  // clear it first; otherwise the retry would re-request what is already on screen.
  const retry = () => {
    if (blocks) {
      setBlocks(null)
      setProvider("")
    } else {
      automatic.reload()
    }
  }

  if (automatic.loading) return <Skeleton className="h-32 w-full" />

  if (!resolved) {
    return (
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 p-4 rounded-xl border-2 border-dashed border-accent-200 bg-gradient-to-r from-accent-50/60 to-white">
        <div className="w-9 h-9 rounded-lg gradient-accent flex items-center justify-center flex-shrink-0">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium text-primary-900">Analysis</p>
          <p className="text-xs text-gray-500">
            Generated from this construct's own scores, thresholds and route profile. Every
            figure in the text traces back to a field in the response.
          </p>
          {error && <p className="text-xs text-red-600 mt-1">{error.message}</p>}
        </div>
        <Button
          variant="gradient"
          size="sm"
          onClick={generate}
          disabled={manual.pending}
          className="flex-shrink-0"
        >
          {manual.pending ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Generating…
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Generate analysis
            </>
          )}
        </Button>
      </div>
    )
  }

  return (
    <div className="rounded-xl border-2 border-accent-200 bg-gradient-to-br from-accent-50/70 to-white overflow-hidden">
      <div className="flex items-center gap-2.5 p-4 border-b border-accent-100">
        <div className="w-9 h-9 rounded-lg gradient-accent flex items-center justify-center flex-shrink-0">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-primary-900">Analysis</p>
          <p className="text-[11px] text-gray-400">
            {resolvedProvider === "template"
              ? "Deterministic template over this construct's own fields — not model output"
              : `provider: ${resolvedProvider}`}
          </p>
        </div>
        {error && (
          <Button variant="ghost" size="sm" className="ml-auto" onClick={retry}>
            Retry
          </Button>
        )}
      </div>

      <div className="p-4 space-y-2.5">
        {resolved.map((block) => (
          <AnalysisBlockCard key={block.id} block={block} />
        ))}
      </div>
    </div>
  )
}

function AnalysisBlockCard({ block }: { block: AnalysisBlock }) {
  const [open, setOpen] = useState(!block.collapsed)

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      <button
        onClick={() => setOpen((current) => !current)}
        className="w-full flex items-center gap-2 p-3 text-left cursor-pointer"
        aria-expanded={open}
      >
        <span className="text-xs font-semibold text-primary-900 flex-1">{block.title}</span>
        <ChevronDown
          className={cn("w-3.5 h-3.5 text-gray-400 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <div className="px-3 pb-3">
          <p className="text-xs text-gray-600 leading-relaxed whitespace-pre-line">
            {block.content}
          </p>
          {block.citations.length > 0 && (
            <p className="text-[10px] text-gray-400 mt-2 font-mono break-all">
              from {block.citations.join(" · ")}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

/** Convenience wrapper used where a caller already holds the detail response. */
export function AnalysisOf({ detail }: { detail: ConstructDetail }) {
  return <AnalysisBlocks constructId={detail.id} routeId={detail.safety.route_id} />
}
