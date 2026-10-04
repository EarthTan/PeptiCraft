import { AlertTriangle, RefreshCw, ServerCrash } from "lucide-react"

import { errorHint, errorTitle, type ApiError } from "@/api/client"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/**
 * The failure state every page shows when a request does not produce data.
 *
 * It separates the four conditions the service distinguishes, because they call for
 * different actions: an unreachable service is a local problem, an unreachable database is a
 * problem on the workstation at the other end of the tunnel, and a failed query is neither.
 * Showing one generic "something went wrong" would send a reader looking in the wrong place.
 */
export function ErrorState({
  error,
  onRetry,
  className,
  compact,
}: {
  error: ApiError
  onRetry?: () => void
  className?: string
  compact?: boolean
}) {
  const hint = errorHint(error)
  const Icon = error.kind === "network" ? ServerCrash : AlertTriangle

  return (
    <div
      className={cn(
        "rounded-xl border border-red-200 bg-red-50/60",
        compact ? "p-4" : "p-6",
        className,
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <Icon className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-red-800">{errorTitle(error)}</p>
          <p className="text-xs text-red-700 mt-1 leading-relaxed break-words">{error.message}</p>

          {hint && (
            <p className="text-xs text-red-600/90 mt-2 leading-relaxed">{hint}</p>
          )}

          {error.detail && error.detail !== error.message && (
            <p className="text-[11px] text-red-500/80 mt-2 font-mono leading-relaxed break-words">
              {error.detail}
            </p>
          )}

          {onRetry && (
            <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
              <RefreshCw className="w-3.5 h-3.5" />
              Retry
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
