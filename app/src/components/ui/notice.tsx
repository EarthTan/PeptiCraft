import type { ReactNode } from "react"
import { AlertTriangle, Info, TriangleAlert } from "lucide-react"

import { cn } from "@/lib/utils"

type NoticeTone = "info" | "caution" | "warning"

const TONE = {
  info: {
    wrap: "border-primary-200 bg-primary-50/60",
    title: "text-primary-900",
    body: "text-primary-700",
    icon: "text-primary-500",
    Icon: Info,
  },
  caution: {
    wrap: "border-amber-200 bg-amber-50",
    title: "text-amber-800",
    body: "text-amber-700",
    icon: "text-amber-500",
    Icon: TriangleAlert,
  },
  warning: {
    wrap: "border-red-200 bg-red-50/70",
    title: "text-red-800",
    body: "text-red-700",
    icon: "text-red-500",
    Icon: AlertTriangle,
  },
} as const

/**
 * A statement about the limits of the data on screen.
 *
 * These are not decoration. Three facts in this platform are true of the data and would be
 * misleading if omitted: every stored construct binds a placeholder scaffold, two of the four
 * function directions hold rows the pipeline has not signed off, and the anti-inflammatory
 * and anti-melanin scores order candidates without measuring activity. Each one travels with
 * the content it qualifies rather than being collected in a disclaimer elsewhere.
 */
export function Notice({
  tone = "caution",
  title,
  children,
  className,
}: {
  tone?: NoticeTone
  title: string
  children?: ReactNode
  className?: string
}) {
  const skin = TONE[tone]
  const Icon = skin.Icon

  return (
    <div className={cn("flex items-start gap-2.5 rounded-lg border p-3", skin.wrap, className)}>
      <Icon className={cn("w-4 h-4 flex-shrink-0 mt-0.5", skin.icon)} />
      <div className="min-w-0 flex-1">
        <p className={cn("text-xs font-semibold", skin.title)}>{title}</p>
        {children && (
          <div className={cn("text-xs leading-relaxed mt-0.5", skin.body)}>{children}</div>
        )}
      </div>
    </div>
  )
}

/** Small inline marker for a value the service reports as ranking-only. */
export function RankingOnlyMarker({ note }: { note?: string }) {
  return (
    <span
      className="text-[10px] text-gray-400"
      title={
        note ??
        "This score orders candidates. The predictor behind it separates functional-looking " +
          "peptides from random fragments rather than measuring activity, so it is not a " +
          "probability."
      }
    >
      ranking only
    </span>
  )
}
