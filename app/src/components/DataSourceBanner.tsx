/**
 * A standing statement of which database answered the page.
 *
 * The service can fall back to a bundled SQLite fixture when the remote Postgres instance is
 * unreachable, and that fallback is what keeps the interface on screen while the far end is
 * down. It is also the one situation in which every number shown is sample data: the fixture
 * holds four hand-made constructs, not the 496 the pipeline produced. A page that renders the
 * fixture without saying so is indistinguishable from a page reporting real results, so the
 * banner is placed in the layout rather than inside a page — it applies to every route,
 * including the ones a reader lands on directly from a shared link.
 *
 * The health check is polled rather than fetched once. Reachability can change while the tab
 * is open, and a banner that pinned itself to "sample data" after the connection came back
 * would be its own kind of wrong.
 */
import { useCallback, useEffect, useState } from "react"
import { Database, RefreshCw } from "lucide-react"

import { fetchHealth } from "@/api"
import type { HealthResponse } from "@/api/types"

const POLL_MS = 30_000

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

  const { backend, fallback_reason: reason, note, host } = health.database
  const offline = Boolean(reason) || backend === "sqlite"

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
              The project database at {host} is not reachable, so the service has fallen back
              to a local sample dataset holding four hand-made constructs. Counts, scores,
              rankings and safety verdicts on every page describe that sample and nothing else.
              {reason ? ` Reported reason: ${reason}.` : ""}
              {note ? ` ${note}` : ""}
            </p>
          </div>
          <button
            onClick={() => void probe()}
            className="flex-shrink-0 inline-flex items-center gap-1 text-xs font-medium text-amber-800 hover:text-amber-900 cursor-pointer"
            title="Check the database again"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry
          </button>
        </div>
      </div>
    </div>
  )
}
