/**
 * Saved build records.
 *
 * A build is a composition rather than a stored row: it answers for a route, a set of
 * directions, a scaffold and a linker at one moment, and nothing of it survives the page
 * being closed. This module keeps the builds worth keeping — the ones a reader wants to
 * come back to, to compare against a later build, or to hand to somebody else.
 *
 * Where the records live
 * ----------------------
 * In the browser, under one key in `localStorage`. The platform is published as static
 * files with no application server behind it, so there is nowhere on the deployed site for
 * a write to land; the FastAPI service that serves the Builder in development is not the
 * thing the site runs against. A record kept here therefore belongs to the device that
 * made it, and the export/import pair is what carries one elsewhere.
 *
 * What a record holds
 * -------------------
 * The parameters that produced the build, the labels those parameters had at the time, the
 * verdict tally, and a trimmed snapshot of the ranked candidates. The labels are stored
 * rather than looked up on read because the library can change: a record has to read the
 * way it was made, not the way the library looks today.
 *
 * The snapshot is trimmed on purpose. A full ranking is a hundred rows of scores and
 * sequences, which is megabytes of `localStorage` for a list that is meant to be read, not
 * re-analyzed. The tally over the whole candidate set is kept exactly, because it is the
 * part that describes the build rather than the page it was shown on.
 */
import type { BuildCounts, BuiltConstruct, SafetyVerdictKind, SequenceSegment } from "@/api/types"

const STORAGE_KEY = "pepticraft.build-records.v1"
const SCHEMA_VERSION = 1

/** How many ranked candidates a record keeps. The rest are counted, not carried. */
const MAX_CANDIDATES = 25

export interface BuildRecordParams {
  /** Function directions the build screened for. */
  direction: string[]
  route_id: string
  scaffold_id: string | null
  linker_id: string | null
  limit: number
}

export interface BuildRecordLabels {
  route: string
  directions: string
  scaffold: string | null
  linker: string | null
}

export interface SavedCandidate {
  id: string
  name: string
  rank: number | null
  direction_label: string
  composite: number | null
  safety_verdict: SafetyVerdictKind | null
  peptide_length: number
  fused_length: number | null
  peptide_sequence: string
  segments: SequenceSegment[]
}

export interface BuildRecord {
  id: string
  title: string
  note: string
  /** ISO timestamp of the moment the record was written. */
  created_at: string
  params: BuildRecordParams
  labels: BuildRecordLabels
  counts: BuildCounts
  /** Candidates the build ranked, before the page was sliced. */
  total: number
  candidates: SavedCandidate[]
  /** Ranked candidates the snapshot did not keep. */
  omitted: number
}

export interface SaveBuildInput {
  title: string
  note: string
  params: BuildRecordParams
  labels: BuildRecordLabels
  counts: BuildCounts
  total: number
  candidates: BuiltConstruct[]
}

export type SaveOutcome =
  | { ok: true; record: BuildRecord }
  | { ok: false; error: string }

// ── Storage ─────────────────────────────────────────────────────────────────

/** Whether this browser will let the page keep anything. Private modes can refuse. */
export function storageAvailable(): boolean {
  try {
    const probe = `${STORAGE_KEY}.probe`
    window.localStorage.setItem(probe, "1")
    window.localStorage.removeItem(probe)
    return true
  } catch {
    return false
  }
}

function isRecord(value: unknown): value is BuildRecord {
  if (!value || typeof value !== "object") return false
  const record = value as Partial<BuildRecord>
  return (
    typeof record.id === "string" &&
    typeof record.title === "string" &&
    typeof record.created_at === "string" &&
    typeof record.params === "object" &&
    record.params !== null &&
    Array.isArray(record.params.direction) &&
    Array.isArray(record.candidates)
  )
}

/** Every stored record, newest first. Unreadable storage yields an empty list. */
export function listBuildRecords(): BuildRecord[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== "object") return []
    const envelope = parsed as { version?: number; records?: unknown }
    if (envelope.version !== SCHEMA_VERSION) return []
    if (!Array.isArray(envelope.records)) return []
    return (envelope.records as unknown[])
      .filter(isRecord)
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
  } catch {
    return []
  }
}

function writeAll(records: BuildRecord[]): string | null {
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ version: SCHEMA_VERSION, records }),
    )
    return null
  } catch (cause) {
    const name = cause instanceof Error ? cause.name : ""
    if (name === "QuotaExceededError" || name === "NS_ERROR_DOM_QUOTA_REACHED") {
      return "The browser's storage for saved builds is full. Delete a record and try again."
    }
    return "This browser refused to keep the record."
  }
}

// ── Mutations ───────────────────────────────────────────────────────────────

function newId(): string {
  const cryptoApi = globalThis.crypto
  if (cryptoApi && typeof cryptoApi.randomUUID === "function") return cryptoApi.randomUUID()
  return `build-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function toCandidate(item: BuiltConstruct): SavedCandidate {
  return {
    id: item.id,
    name: item.name,
    rank: item.rank,
    direction_label: item.direction_label,
    composite: item.composite,
    safety_verdict: item.safety_verdict,
    peptide_length: item.peptide_length,
    fused_length: item.fused_length,
    peptide_sequence: item.peptide_sequence,
    segments: item.segments ?? [],
  }
}

/** Write a build to the store, keeping the twenty-five highest-ranked candidates. */
export function saveBuildRecord(input: SaveBuildInput): SaveOutcome {
  const kept = input.candidates.slice(0, MAX_CANDIDATES)
  const record: BuildRecord = {
    id: newId(),
    title: input.title.trim() || "Untitled build",
    note: input.note.trim(),
    created_at: new Date().toISOString(),
    params: input.params,
    labels: input.labels,
    counts: input.counts,
    total: input.total,
    candidates: kept.map(toCandidate),
    omitted: Math.max(0, input.candidates.length - kept.length),
  }

  const records = [record, ...listBuildRecords()]
  const error = writeAll(records)
  if (error) return { ok: false, error }
  return { ok: true, record }
}

/** Change a record's title or note. Returns the updated list, or null on failure. */
export function updateBuildRecord(
  id: string,
  patch: { title?: string; note?: string },
): BuildRecord[] | null {
  const records = listBuildRecords()
  const index = records.findIndex((record) => record.id === id)
  if (index === -1) return null
  const current = records[index]
  records[index] = {
    ...current,
    title: patch.title !== undefined ? patch.title.trim() || current.title : current.title,
    note: patch.note !== undefined ? patch.note.trim() : current.note,
  }
  const error = writeAll(records)
  return error ? null : records
}

/** Remove one record. Returns the remaining list, or null on failure. */
export function deleteBuildRecord(id: string): BuildRecord[] | null {
  const records = listBuildRecords().filter((record) => record.id !== id)
  const error = writeAll(records)
  return error ? null : records
}

// ── Moving records between devices ──────────────────────────────────────────

/** The export as a string. The download itself is the caller's business. */
export function serialiseRecords(records: BuildRecord[]): string {
  return JSON.stringify({ version: SCHEMA_VERSION, exported_at: new Date().toISOString(), records }, null, 2)
}

/**
 * Read an export back.
 *
 * Records that do not parse are dropped rather than refused: an export is a file a person
 * may have edited, and one malformed entry should not cost the rest. The version has to
 * match, because a record's shape is what the interface reads.
 */
export function parseRecords(text: string): { records: BuildRecord[]; skipped: number } {
  const parsed = JSON.parse(text) as unknown
  if (!parsed || typeof parsed !== "object") {
    throw new Error("The file does not contain a build-record export.")
  }
  const envelope = parsed as { version?: number; records?: unknown }
  if (envelope.version !== SCHEMA_VERSION) {
    throw new Error(
      `This export was written in version ${String(envelope.version ?? "?")}; this build reads version ${SCHEMA_VERSION}.`,
    )
  }
  if (!Array.isArray(envelope.records)) {
    throw new Error("The file does not contain a list of build records.")
  }
  const all = envelope.records as unknown[]
  const records = all.filter(isRecord)
  return { records, skipped: all.length - records.length }
}

/** Merge imported records into the store, keeping both sides. */
export function importRecords(records: BuildRecord[]): BuildRecord[] | null {
  const existing = listBuildRecords()
  const seen = new Set(existing.map((record) => record.id))
  const merged = [...existing]
  for (const record of records) {
    if (seen.has(record.id)) continue
    seen.add(record.id)
    merged.push(record)
  }
  merged.sort((a, b) => b.created_at.localeCompare(a.created_at))
  const error = writeAll(merged)
  return error ? null : merged
}
