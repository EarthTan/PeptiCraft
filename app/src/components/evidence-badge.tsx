import { useState } from "react"
import { Badge } from "@/components/ui/badge"

const EVIDENCE_LEVELS = [
  ["E1", "Purified protein, physicochemical or cell-free experiments"],
  ["E2", "Cell experiments"],
  ["E3", "Animal experiments"],
  ["E4", "Human use or controlled clinical studies"],
  ["E5", "Regulatory review and post-market safety data"],
] as const

export function EvidenceBadge({ level }: { level: string }) {
  const [open, setOpen] = useState(false)
  const description = EVIDENCE_LEVELS.find(([id]) => id === level)?.[1] ?? "Evidence level not recorded"
  return <span className="relative inline-flex group/evidence" onMouseLeave={() => setOpen(false)}>
    <span tabIndex={0} role="button" aria-label={`${level}: ${description}`} aria-expanded={open}
      className="cursor-help rounded-full" onClick={event => { event.preventDefault(); event.stopPropagation(); setOpen(!open) }}
      onBlur={() => setOpen(false)} onKeyDown={event => {
        if (event.key === "Escape") setOpen(false)
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); event.stopPropagation(); setOpen(!open) }
      }}><Badge variant="accent">{level}</Badge></span>
    <span role="tooltip" className={`absolute left-0 bottom-full mb-2 z-30 w-64 rounded-xl bg-primary-950 p-3 text-xs leading-relaxed text-white shadow-lg pointer-events-none ${open ? "block" : "hidden group-hover/evidence:block group-focus-within/evidence:block"}`}>
      <strong>{level}</strong> - {description}
    </span>
  </span>
}

export function EvidenceGuide() {
  return <details className="mt-4 rounded-xl border border-primary-100 bg-primary-50/50 p-4 text-sm">
    <summary className="cursor-pointer font-semibold text-primary-900">Understanding scaffold evidence: E1-E5</summary>
    <p className="mt-3 text-gray-600">Each grade records the highest documented evidence level for the reported material and application.</p>
    <dl className="mt-3 grid sm:grid-cols-2 gap-3">{EVIDENCE_LEVELS.map(([level, meaning]) => <div key={level} className="flex gap-3"><dt className="font-semibold text-primary-700">{level}</dt><dd className="text-gray-600">{meaning}</dd></div>)}</dl>
  </details>
}

export function EvidenceLegend() {
  return <aside className="my-5 rounded-xl border border-primary-100 bg-primary-50/50 p-4" aria-label="Scaffold evidence levels">
    <p className="text-sm font-semibold text-primary-900 mb-3">Scaffold evidence levels</p>
    <dl className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">{EVIDENCE_LEVELS.map(([level, meaning]) => <div key={level}><dt className="text-xs font-bold text-primary-700">{level}</dt><dd className="text-xs text-gray-600 leading-relaxed mt-1">{meaning}</dd></div>)}</dl>
  </aside>
}
