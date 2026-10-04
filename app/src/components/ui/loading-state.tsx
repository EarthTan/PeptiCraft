import { Loader2 } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

/** An in-place spinner for a section that is being re-fetched. */
export function LoadingBlock({ label, className }: { label?: string; className?: string }) {
  return (
    <div className={cn("flex items-center justify-center gap-2 py-10", className)}>
      <Loader2 className="w-4 h-4 animate-spin text-primary-400" />
      <span className="text-sm text-gray-500">{label ?? "Loading"}</span>
    </div>
  )
}

/** Placeholder rows that hold the layout while a list loads. */
export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="rounded-xl border border-gray-200 bg-white p-5">
          <div className="flex items-center gap-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-14" />
          </div>
          <Skeleton className="h-3 w-2/5 mt-3" />
          <div className="flex gap-3 mt-4">
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-8 w-16" />
          </div>
        </div>
      ))}
    </div>
  )
}

/** Placeholder cards for the grid layouts. */
export function CardGridSkeleton({ cards = 6, columns = 2 }: { cards?: number; columns?: number }) {
  return (
    <div
      className={cn(
        "grid gap-4",
        columns === 3 ? "sm:grid-cols-2 lg:grid-cols-3" : "md:grid-cols-2",
      )}
    >
      {Array.from({ length: cards }).map((_, index) => (
        <div key={index} className="rounded-xl border border-gray-200 bg-white p-5">
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-3 w-1/3 mt-2" />
          <Skeleton className="h-3 w-full mt-4" />
          <Skeleton className="h-3 w-4/5 mt-2" />
        </div>
      ))}
    </div>
  )
}
