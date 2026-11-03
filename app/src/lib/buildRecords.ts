/**
 * Build history.
 *
 * A build is a composition rather than a stored row: it answers for a route, a set of
 * directions, a scaffold and a linker at one moment, and nothing of it survives the page
 * being closed. This module keeps the builds that were actually run, so the same choices
 * can be picked up again later or compared against a run made after the library changed.
 *
 * Automatic, not on demand
 * ------------------------
 * Every build that reaches its results is recorded. A record belongs to the build that was
 * started from the Builder's entry point — its session — and within that session it is keyed
 * by the four choices that produced it. Running the same combination again in the same
 * session updates the record's figures and its last-built time instead of adding a
 * near-duplicate beside it; `runs` counts those repetitions. A new session always starts a
 * new record, because starting a build is the act that names it.
 *
 * Where the records live
 * ----------------------
 * In the browser, under one key in `localStorage`. The platform is published as static
 * files with no application server behind it, so there is nowhere on the deployed site for
 * a write to land; the FastAPI service that serves the Builder in development is not the
 * thing the site runs against. A record therefore belongs to the device that made it, and
 * the export/import pair is what carries one elsewhere.
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

const STORAGE_KEY = "pepticraft.build-records.v2"
const LEGACY_KEY = "pepticraft.build-records.v1"
const SCHEMA_VERSION = 2

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
  /**
   * The Builder session the record was made in. A session begins when a build is started and
   * opens again when the record is loaded back into the Builder, which is what makes "the
   * same combination, built again" mean the same build rather than a new one.
   */
  session_id: string
  /** The name given to the build when it was started. Editable afterwards. */
  title: string
  note: string
  /** First time this combination was built. */
  created_at: string
  /** Most recent time it was built. The list is ordered by this. */
  built_at: string
  /** How many times this combination has been built. */
  runs: number
  /** Identifies the combination. Two builds with the same signature are one record. */
  signature: string
  params: BuildRecordParams
  labels: BuildRecordLabels
  counts: BuildCounts
  /** Candidates the build ranked, before the page was sliced. */
  total: number
  candidates: SavedCandidate[]
  /** Ranked candidates the snapshot did not keep. */
  omitted: number
}

export interface RecordBuildInput {
  /** The session the build is being run in. */
  session_id: string
  /** The name of the build in progress. */
  title: string
  params: BuildRecordParams
  labels: BuildRecordLabels
  counts: BuildCounts
  total: number
  candidates: BuiltConstruct[]
}

export type RecordOutcome =
  | { ok: true; record: BuildRecord; created: boolean }
  | { ok: false; error: string }

/**
 * What makes two runs within one build the same run.
 *
 * The four choices that drive the result — route, directions, scaffold, linker — and
 * nothing else. `limit` is left out because it slices a finished ranking rather than
 * changing it, and `offset` never reaches a record. Directions are sorted so that choosing
 * the same pair in the other order does not produce a second entry.
 *
 * A signature says nothing on its own: two builds started separately at different times are
 * different records even when their signatures match. The session is the other half of the
 * identity.
 */
export function signatureOf(params: BuildRecordParams): string {
  return [
    params.route_id,
    [...params.direction].sort().join(","),
    params.scaffold_id ?? "",
    params.linker_id ?? "",
  ].join("|")
}

// ── Storage ─────────────────────────────────────────────────────────────────

function isRecord(value: unknown): value is BuildRecord {
  if (!value || typeof value !== "object") return false
  const record = value as Partial<BuildRecord>
  return (
    typeof record.id === "string" &&
    typeof record.session_id === "string" &&
    typeof record.title === "string" &&
    typeof record.built_at === "string" &&
    typeof record.params === "object" &&
    record.params !== null &&
    Array.isArray(record.params.direction) &&
    Array.isArray(record.candidates)
  )
}

/**
 * Bring a record written before timestamps were split into `created_at` / `built_at`, and
 * before `signature` and `runs` existed, up to the current shape.
 *
 * The fields are derivable, so an older record is filled in rather than discarded. It was
 * written by an earlier build of the interface on this machine, which is the only way an
 * older record can exist at all.
 */
function migrate(value: unknown): BuildRecord | null {
  if (!value || typeof value !== "object") return null
  const raw = value as Partial<BuildRecord> & { created_at?: string }
  if (
    typeof raw.id !== "string" ||
    typeof raw.title !== "string" ||
    !raw.params ||
    !Array.isArray(raw.params.direction) ||
    !Array.isArray(raw.candidates)
  ) {
    return null
  }
  const stamp = raw.built_at ?? raw.created_at ?? new Date().toISOString()
  return {
    id: raw.id,
    // A record written before sessions existed was the record of its own build, so its own
    // id stands in for the session and nothing merges with it.
    session_id: raw.session_id ?? raw.id,
    title: raw.title,
    note: raw.note ?? "",
    created_at: raw.created_at ?? stamp,
    built_at: stamp,
    runs: raw.runs ?? 1,
    signature: raw.signature ?? signatureOf(raw.params),
    params: raw.params,
    labels: raw.labels ?? { route: "", directions: "", scaffold: null, linker: null },
    counts: raw.counts ?? {
      clear: 0,
      borderline: 0,
      vetoed: 0,
      indeterminate: 0,
      ranked: 0,
      without_composite: 0,
    },
    total: raw.total ?? 0,
    candidates: raw.candidates,
    omitted: raw.omitted ?? 0,
  }
}

/** Every recorded build, most recently built first. Unreadable storage yields none. */
export function listBuildRecords(): BuildRecord[] {
  const current = readEnvelope(STORAGE_KEY)
  const legacy = readEnvelope(LEGACY_KEY)
  if (legacy.length === 0) return sortRecords(current)

  // Records written before the history was automatic are merged rather than read only when
  // the current key is empty: the first build recorded under the new key would otherwise
  // hide everything that came before it. The merge is one-time, and the old key is dropped
  // once its contents are on the current one.
  const merged = sortRecords(mergeHistory(current, legacy))
  if (writeAll(merged) === null) {
    try {
      window.localStorage.removeItem(LEGACY_KEY)
    } catch {
      // Leaving the old key behind is harmless: the next read merges it again, and the
      // merge is idempotent.
    }
  }
  return merged
}

function readEnvelope(key: string): BuildRecord[] {
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== "object") return []
    const envelope = parsed as { records?: unknown }
    if (!Array.isArray(envelope.records)) return []
    return (envelope.records as unknown[])
      .map((entry) => (isRecord(entry) ? entry : migrate(entry)))
      .filter((record): record is BuildRecord => record !== null)
  } catch {
    return []
  }
}

/**
 * Most recently built first, with ties broken so the order is not left to chance.
 *
 * Two builds can land in the same millisecond when a page records them back to back, and
 * `sort` alone would then keep whichever order the array happened to hold. New records are
 * put at the front of the array, so falling back to the array's own order is what keeps the
 * newest on top.
 */
function sortRecords(records: BuildRecord[]): BuildRecord[] {
  return [...records].sort((a, b) => b.built_at.localeCompare(a.built_at))
}

/**
 * Records from `extra` that are not already in `primary`.
 *
 * Identity is the id, and otherwise the session together with the combination: two records
 * of the same combination made in different builds are different builds, and both belong in
 * the list.
 */
function mergeHistory(primary: BuildRecord[], extra: BuildRecord[]): BuildRecord[] {
  const byId = new Set(primary.map((record) => record.id))
  const byRun = new Set(primary.map((record) => `${record.session_id}|${record.signature}`))
  const out = [...primary]
  for (const record of extra) {
    const run = `${record.session_id}|${record.signature}`
    if (byId.has(record.id) || byRun.has(run)) continue
    byId.add(record.id)
    byRun.add(run)
    out.push(record)
  }
  return out
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
      return "The browser's storage for build history is full. Delete a record and try again."
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

/**
 * Record a build that has just been run.
 *
 * The same combination built again inside the same session updates its record rather than
 * adding a second one: the figures and the snapshot move to the new run, `built_at`
 * advances, and `runs` counts the repetitions. A combination built in a later session is a
 * different build under a different name, so it becomes its own record. The title is taken
 * at creation only — a name a reader chose is not something a later run gets to overwrite.
 */
export function recordBuild(input: RecordBuildInput): RecordOutcome {
  const kept = input.candidates.slice(0, MAX_CANDIDATES)
  const snapshot = {
    params: input.params,
    labels: input.labels,
    counts: input.counts,
    total: input.total,
    candidates: kept.map(toCandidate),
    omitted: Math.max(0, input.candidates.length - kept.length),
  }
  const now = new Date().toISOString()
  const signature = signatureOf(input.params)
  const records = listBuildRecords()
  const index = records.findIndex(
    (record) => record.session_id === input.session_id && record.signature === signature,
  )

  let record: BuildRecord
  let created = false

  if (index >= 0) {
    const existing = records[index]
    record = { ...existing, ...snapshot, built_at: now, runs: existing.runs + 1 }
    records[index] = record
  } else {
    created = true
    record = {
      id: newId(),
      session_id: input.session_id,
      title: input.title.trim() || "Untitled build",
      note: "",
      created_at: now,
      built_at: now,
      runs: 1,
      signature,
      ...snapshot,
    }
    // In front, so a tie on `built_at` leaves the newest entry first after the sort.
    records.unshift(record)
  }

  const error = writeAll(sortRecords(records))
  if (error) return { ok: false, error }
  return { ok: true, record, created }
}

/**
 * Rename every record made in one build.
 *
 * A build's name is asked for once, but it can be changed while the build is on screen, and
 * the records already made under it are the same build — a header saying one thing while the
 * history says another would be a disagreement about which build is which. Returns the
 * updated list, or null when nothing changed or the write failed.
 */
export function renameSession(sessionId: string, title: string): BuildRecord[] | null {
  const name = title.trim()
  if (!name) return null
  const records = listBuildRecords()
  let changed = false
  for (let index = 0; index < records.length; index += 1) {
    if (records[index].session_id !== sessionId || records[index].title === name) continue
    records[index] = { ...records[index], title: name }
    changed = true
  }
  if (!changed) return null
  const error = writeAll(records)
  return error ? null : records
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

/** Remove one record. Returns the remaining list, or null on failure. */export function deleteBuildRecord(id: string): BuildRecord[] | null {
  const records = listBuildRecords().filter((record) => record.id !== id)
  const error = writeAll(records)
  return error ? null : records
}

// ── Moving records between devices ──────────────────────────────────────────

/** The export as a string. The download itself is the caller's business. */
export function serialiseRecords(records: BuildRecord[]): string {
  return JSON.stringify(
    { version: SCHEMA_VERSION, exported_at: new Date().toISOString(), records },
    null,
    2,
  )
}

/**
 * Read an export back.
 *
 * Records that do not parse are dropped rather than refused: an export is a file a person
 * may have edited, and one malformed entry should not cost the rest.
 */
export function parseRecords(text: string): { records: BuildRecord[]; skipped: number } {
  const parsed = JSON.parse(text) as unknown
  if (!parsed || typeof parsed !== "object") {
    throw new Error("The file does not contain a build-history export.")
  }
  const envelope = parsed as { version?: number; records?: unknown }
  if (!Array.isArray(envelope.records)) {
    throw new Error("The file does not contain a list of builds.")
  }
  // A v1 export is the same records under the older field names; anything newer is not
  // something this build can read, and is refused rather than half-understood.
  if (envelope.version !== undefined && envelope.version > SCHEMA_VERSION) {
    throw new Error(
      `This export was written in version ${envelope.version}; this build reads up to version ${SCHEMA_VERSION}.`,
    )
  }
  const all = envelope.records as unknown[]
  const records = all
    .map((entry) => (isRecord(entry) ? entry : migrate(entry)))
    .filter((record): record is BuildRecord => record !== null)
  return { records, skipped: all.length - records.length }
}

/**
 * Merge imported records into the history, keeping both sides.
 *
 * A record already held is not duplicated: the one on disk wins, on the grounds that it is
 * the one this browser has been updating. Two builds of the same combination made in
 * different builds are not the same entry, so both are kept.
 */
export function importRecords(records: BuildRecord[]): BuildRecord[] | null {
  const merged = sortRecords(mergeHistory(listBuildRecords(), records))
  const error = writeAll(merged)
  return error ? null : merged
}
