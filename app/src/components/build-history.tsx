import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  deleteBuildRecord,
  importRecords,
  parseRecords,
  serialiseRecords,
  updateBuildRecord,
  type BuildRecord,
} from "@/lib/buildRecords"
import { Download, FolderOpen, Trash2, Upload, X } from "lucide-react"

/** "22:43" for something built today, "11/2 22:43" for anything older. */
function stamp(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  const now = new Date()
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  return sameDay
    ? date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
    : `${date.getMonth() + 1}/${date.getDate()} ${date.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      })}`
}

/**
 * The build history.
 *
 * Every build that reaches its results is recorded without being asked, so this panel is a
 * record of what has been run rather than a shelf of things that were saved. Each build
 * started from the Builder is a line of its own; building one of its combinations again
 * refreshes that line's figures and its time instead of adding a second one.
 *
 * Loading an entry puts its parameters back into the Builder and builds it again, which is
 * the point of keeping it - the record remembers the question, and the answer comes from
 * the library as it stands now.
 *
 * The records live in this browser. Export and import are what carry them to another
 * machine, and the panel says so rather than leaving it to be discovered.
 */
export function BuildHistoryPanel({
  open,
  onClose,
  records,
  onRecordsChange,
  onLoad,
}: {
  open: boolean
  onClose: () => void
  records: BuildRecord[]
  onRecordsChange: (records: BuildRecord[]) => void
  onLoad: (record: BuildRecord) => void
}) {
  const [message, setMessage] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onClose])

  if (!open) return null

  const rename = (record: BuildRecord, title: string) => {
    const next = updateBuildRecord(record.id, { title })
    if (next) onRecordsChange(next)
  }

  const remove = (record: BuildRecord) => {
    const next = deleteBuildRecord(record.id)
    if (next) {
      onRecordsChange(next)
      setMessage(`Removed “${record.title}”.`)
    } else {
      setMessage("The record could not be removed.")
    }
  }

  const exportFile = () => {
    const blob = new Blob([serialiseRecords(records)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `pepticraft-build-history-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    setMessage(`Exported ${records.length} record${records.length === 1 ? "" : "s"}.`)
  }

  const importFile = async (file: File) => {
    try {
      const text = await file.text()
      const { records: parsed, skipped } = parseRecords(text)
      const next = importRecords(parsed)
      if (!next) {
        setMessage("The records could not be added to this browser's storage.")
        return
      }
      onRecordsChange(next)
      setMessage(
        skipped > 0
          ? `Imported ${parsed.length} record${parsed.length === 1 ? "" : "s"}; ${skipped} entr${skipped === 1 ? "y was" : "ies were"} skipped.`
          : `Imported ${parsed.length} record${parsed.length === 1 ? "" : "s"}.`,
      )
    } catch (cause) {
      setMessage(
        cause instanceof Error ? cause.message : "The file could not be read as a build-history export.",
      )
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 sm:p-8">
      <div className="absolute inset-0 bg-primary-900/40" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Build history"
        className="relative w-full max-w-2xl max-h-full overflow-y-auto rounded-xl border border-gray-200 bg-white shadow-xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-gray-200 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-primary-900">Build history</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {records.length} build{records.length === 1 ? "" : "s"} recorded in this browser
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close build history">
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="px-5 py-4 space-y-2.5">
          {records.length === 0 && (
            <p className="text-sm text-gray-500 py-8 text-center">
              No build has been run yet. Each build is recorded here once its results appear.
            </p>
          )}

          {records.map((record) => (
            <div
              key={record.id}
              className="rounded-lg border border-gray-200 bg-surface-alt/40 p-3"
            >
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <Input
                    defaultValue={record.title}
                    aria-label="Build name"
                    onBlur={(event) => {
                      if (event.target.value.trim() && event.target.value !== record.title) {
                        rename(record, event.target.value)
                      }
                    }}
                    className="h-8 border-transparent bg-transparent px-1 text-sm font-semibold text-primary-900 focus:bg-white"
                  />
                  <p className="text-xs text-gray-500 mt-0.5 truncate">
                    {[
                      record.labels.route,
                      record.labels.directions,
                      record.labels.scaffold,
                      record.labels.linker,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  <p className="text-[11px] text-gray-400 mt-1">
                    Built {stamp(record.built_at)}
                    {record.runs > 1 && ` · ${record.runs} times`} · {record.counts.ranked}{" "}
                    candidates ranked · {record.counts.clear} clear · {record.counts.vetoed} vetoed
                    {record.omitted > 0 && ` · ${record.omitted} beyond the snapshot`}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <Button variant="secondary" size="sm" onClick={() => onLoad(record)}>
                    <FolderOpen className="w-4 h-4" />
                    Load
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => remove(record)}
                    aria-label={`Delete ${record.title}`}
                  >
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-gray-200 px-5 py-3">
          <p className="text-[11px] text-gray-400 leading-relaxed">
            Kept in this browser. Export to move the history to another machine.
          </p>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button variant="outline" size="sm" onClick={() => fileInput.current?.click()}>
              <Upload className="w-4 h-4" />
              Import
            </Button>
            <Button variant="outline" size="sm" onClick={exportFile} disabled={records.length === 0}>
              <Download className="w-4 h-4" />
              Export
            </Button>
            <input
              ref={fileInput}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ""
                if (file) void importFile(file)
              }}
            />
          </div>
        </div>

        {message && (
          <p className="border-t border-gray-200 px-5 py-2 text-xs text-gray-500">{message}</p>
        )}
      </div>
    </div>
  )
}

/**
 * The naming step, shown once as the Builder is entered.
 *
 * A build gets a name before its choices are made, because the name is what the history
 * line will be read by: by the time the results are on screen, every build in the list
 * would otherwise be called after its route and its scaffold, which is the one thing all
 * the similar-looking entries have in common.
 */
export function BuildNameDialog({
  open,
  initialValue,
  onSubmit,
}: {
  open: boolean
  initialValue: string
  onSubmit: (title: string) => void
}) {
  const [value, setValue] = useState(initialValue)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    setValue(initialValue)
    // The field is the only thing on screen; focusing it saves a click.
    const timer = window.setTimeout(() => input.current?.select(), 30)
    return () => window.clearTimeout(timer)
  }, [open, initialValue])

  if (!open) return null

  const submit = () => onSubmit(value.trim() || initialValue)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-primary-900/40" aria-hidden="true" />
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="build-name-title"
        className="relative w-full max-w-md rounded-xl border border-gray-200 bg-white p-5 shadow-xl"
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
      >
        <h2 id="build-name-title" className="text-base font-semibold text-primary-900">
          Name this build
        </h2>
        <p className="text-xs text-gray-500 mt-1 leading-relaxed">
          Every build you run is recorded in the history under this name. It can be changed
          later.
        </p>
        <Input
          ref={input}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className="mt-3"
          aria-label="Build name"
        />
        <div className="flex justify-end gap-2 mt-4">
          <Button type="submit" variant="gradient" size="sm">
            Start building
          </Button>
        </div>
      </form>
    </div>
  )
}
