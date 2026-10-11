/**
 * A standing statement of which source answered the page.
 *
 * There are two ways every number on the site can become sample data. The service can fall
 * back to the bundled SQLite fixture when the remote Postgres instance is unreachable — that
 * fallback is what keeps the interface on screen while the far end is down, and it is the one
 * situation in a live service where every number shown is sample data. And a static
 * deployment can be built from an export that was itself made from the fixture, which is the
 * same failure with no runtime event attached to it.
 *
 * The fixture holds four hand-made constructs, not the 496 the pipeline produced. A page that
 * renders it without saying so is indistinguishable from a page reporting real results, so
 * the banner is placed in the layout rather than inside a page — it applies to every route,
 * including the ones a reader lands on directly from a shared link.
 *
 * The health check is polled rather than fetched once. Reachability can change while the tab
 * is open, and a banner that pinned itself to "sample data" after the connection came back
 * would be its own kind of wrong. A static export cannot change, so that case gets no retry.
 */
import { useCallback, useEffect, useState } from "react"
import { Database, RefreshCw } from "lucide-react"

import { fetchHealth } from "@/api"
import type { HealthResponse } from "@/api/types"

const POLL_MS = 30_000

/**
 * What the banner says, and whether it says anything.
 *
 * Two different situations put sample data on the page and they need different sentences.
 * A live service that could not reach the database and fell back to the fixture is a
 * condition that can change while the tab is open, so it names the host it failed to reach
 * and offers a retry. A static export made from the fixture cannot change at all — the files
 * are what they are — so it says that instead, and the retry button would be a lie.
 */
function describe(health: HealthResponse): { offline: boolean; staticExport: boolean } {
  const { backend, fallback_reason: reason } = health.database
  const staticExport = health.source_backend === "sqlite"
  return { offline: Boolean(reason) || backend === "sqlite" || staticExport, staticExport }
}

export function DataSourceBanner() {
  const [health, setHealth] = useState<HealthResponse | null>(null)

  const probe = useCallback(async () => {
    try {
      setHealth(await fetchHealth())
    } catch {
      // A failed probe is not news: whichever page requested data already reports an
      // unreachable service through its own error state. The banner stays quiet so it does
      // not duplicate the same failure in a second place.
      return
    }
  }, [])

  useEffect(() => {
    void probe()
    const timer = setInterval(() => void probe(), POLL_MS)
    return () => clearInterval(timer)
  }, [probe])

  if (!health) return null

  const { note } = health.database
  const { offline, staticExport } = describe(health)

  if (!offline) return null

  return (
    <div className="border-b border-amber-200 bg-amber-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5">
        <div className="flex items-start gap-2.5">
          <Database className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-600" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-amber-900">
              Showing sample data, not pipeline results
            </p>
            <p className="text-xs leading-relaxed text-amber-800">
              {staticExport ? (
                <>
                  This deployment reads a static snapshot that was exported from the local
                  sample dataset rather than from the project database. The sample holds four
                  hand-made constructs, and the counts, scores, rankings and safety verdicts
                  on the construct pages describe those four and nothing else. The scaffold
                  library beside them is the curated set of patented protein sequences rather
                  than sample data.
                </>
              ) : (
                <>
                  The project database at {health.database.host} is not reachable, so the
                  service has fallen back to a local sample dataset holding four hand-made
                  constructs. The counts, scores, rankings and safety verdicts on the construct
                  pages describe those four and nothing else.
                </>
              )}
              {health.database.fallback_reason
                ? ` Reported reason: ${health.database.fallback_reason}.`
                : ""}
              {note ? ` ${note}` : ""}
            </p>
          </div>
          {!staticExport && (
            <button
              onClick={() => void probe()}
              className="flex-shrink-0 inline-flex items-center gap-1 text-xs font-medium text-amber-800 hover:text-amber-900 cursor-pointer"
              title="Check the database again"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
