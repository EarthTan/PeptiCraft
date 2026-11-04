import { useId, useRef, useState } from "react"
import { Clock, Search } from "lucide-react"

const STORAGE_KEY = "pepticraft.library.search-history.v1"
const HISTORY_LIMIT = 10
function readHistory(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]")
    return Array.isArray(value) ? [...new Set(value.filter((item): item is string => typeof item === "string" && !!item.trim()))].slice(0, HISTORY_LIMIT) : []
  } catch { return [] }
}

export function SearchWithHistory({ onCommit }: { onCommit: (term: string) => void }) {
  const [term, setTerm] = useState("")
  const [history, setHistory] = useState(readHistory)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const input = useRef<HTMLInputElement>(null)
  const listId = useId()
  const save = (next: string[]) => {
    setHistory(next)
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch { /* Search still works without storage. */ }
  }
  const commit = (value: string) => {
    const trimmed = value.trim()
    setTerm(trimmed)
    onCommit(trimmed)
    if (trimmed) save([trimmed, ...history.filter(item => item !== trimmed)].slice(0, HISTORY_LIMIT))
    setOpen(false)
    setActive(-1)
  }
  return <div className="relative flex-1 min-w-0 w-full sm:min-w-[15rem] max-w-md">
    <Search className="w-3.5 h-3.5 absolute left-2.5 top-3 text-gray-400 pointer-events-none" />
    <input ref={input} type="text" role="combobox" autoComplete="off" aria-autocomplete="none" aria-expanded={open && history.length > 0} aria-controls={listId} aria-activedescendant={open && active >= 0 ? `${listId}-${active}` : undefined}
      value={term} onChange={event => { setTerm(event.target.value); setActive(-1); setOpen(true) }} onFocus={() => setOpen(true)}
      onBlur={() => commit(term)} onKeyDown={event => {
        if (event.key === "Escape") { setOpen(false); setActive(-1) }
        if (event.key === "ArrowDown" && history.length) { event.preventDefault(); setOpen(true); setActive(index => Math.min(index + 1, history.length - 1)) }
        if (event.key === "ArrowUp" && history.length) { event.preventDefault(); setActive(index => Math.max(index - 1, 0)) }
        if (event.key === "Enter") { event.preventDefault(); commit(open && active >= 0 ? history[active] : term) }
      }} placeholder="Peptide sequence, source or accession" aria-label="Search constructs"
      className="w-full pl-8 pr-16 py-1.5 rounded-lg border border-gray-200 bg-white text-xs text-gray-700 placeholder:text-gray-400 focus:outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-200" />
    {term && <button type="button" onMouseDown={event => event.preventDefault()} onClick={() => { commit(""); input.current?.focus() }} className="absolute right-2 top-2 text-[11px] text-gray-500 hover:text-primary-700">Clear</button>}
    {open && history.length > 0 && <div className="absolute top-full left-0 right-0 mt-2 z-30 rounded-xl border border-gray-200 bg-white shadow-lg overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 text-xs text-gray-500"><span>Recent searches</span><button type="button" onMouseDown={event => event.preventDefault()} onClick={() => { save([]); setActive(-1); setOpen(false) }}>Clear history</button></div>
      <ul id={listId} role="listbox" aria-label="Recent searches">{history.map((item, index) => <li key={item} id={`${listId}-${index}`} role="option" aria-selected={active === index}>
        <button type="button" tabIndex={-1} onMouseDown={event => event.preventDefault()} onClick={() => commit(item)} className={`flex items-center gap-2 w-full px-3 py-2 text-left text-sm hover:bg-primary-50 ${active === index ? "bg-primary-50 text-primary-800" : "text-gray-600"}`}><Clock size={14} className="shrink-0" /><span className="truncate">{item}</span></button>
      </li>)}</ul>
    </div>}
  </div>
}
