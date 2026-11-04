import type { ReactNode } from "react"
import { AlertTriangle, ChevronRight, Info, TriangleAlert } from "lucide-react"

import { GLOSSARY } from "@/lib/glossary"
import { cn } from "@/lib/utils"

import { InfoTip } from "./tooltip"

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
 * These are not decoration. Facts about the platform that are true of the data and would be
 * misleading if omitted travel with the content they qualify: two of the four function
 * directions hold rows the pipeline has not signed off, the anti-inflammatory and anti-melanin
 * scores order candidates without measuring activity, and a stored scaffold binding records
 * the application route's default scaffold rather than a pairing the pipeline chose. Each one
 * sits beside what it qualifies rather than being collected in a disclaimer elsewhere.
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

/**
 * The same statement, folded away until it is asked for.
 *
 * A notice that travels with a block of results can crowd it out: three paragraphs of
 * qualification above a list of candidates push the candidates below the fold. Folding the
 * notice keeps the qualification attached to what it qualifies while leaving the results
 * visible, and the title alone still says what the note is about, so nothing is hidden
 * behind an unlabelled control.
 */
export function CollapsibleNotice({
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
    <details className={cn("group rounded-lg border", skin.wrap, className)}>
      <summary className="flex items-center gap-2.5 cursor-pointer list-none p-3 [&::-webkit-details-marker]:hidden">
        <Icon className={cn("w-4 h-4 flex-shrink-0", skin.icon)} />
        <span className={cn("text-xs font-semibold flex-1 min-w-0", skin.title)}>{title}</span>
        <ChevronRight className={cn(
          "w-4 h-4 flex-shrink-0 transition-transform group-open:rotate-90",
          skin.icon,
        )} />
      </summary>
      {children && (
        <div className={cn("px-3 pb-3 ml-[26px] text-xs leading-relaxed", skin.body)}>{children}</div>
      )}
    </details>
  )
}

/** Small inline marker for a value the service reports as ranking-only. */
export function RankingOnlyMarker({ note }: { note?: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-[10px] text-gray-400">ranking only</span>
      <InfoTip content={note ?? GLOSSARY.ranking_only} />
    </span>
  )
}
