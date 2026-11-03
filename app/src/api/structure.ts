/**
 * Predicted structures, read from the object store.
 *
 * Why a separate store
 * --------------------
 * A structure is a megabyte-scale artefact and there are thousands of them; the site's own
 * deployment carries a twenty-thousand-file ceiling, which a few thousand PDB files would
 * exhaust. The files therefore live in an R2 bucket, and this module is the only place that
 * knows where.
 *
 * What lives in the bucket
 * ------------------------
 *   structure_lookup.json    `construct_id|scaffold_id|linker_id` → `structure_id`
 *   structures.json          per-structure metadata: chain length, whole-chain confidence,
 *                            and the confidence restricted to the peptide's own residues
 *   structures/<id>.pdb      the coordinate file, named by the same content-addressed id the
 *                            lookup uses, so a page never has to guess a filename
 *
 * The bucket is optional. When `VITE_STRUCTURE_BASE_URL` is unset the platform behaves as
 * before the feature existed and the viewer renders nothing; a structure that has not been
 * computed yet is reported as such rather than shown as an empty frame.
 */

/** One structure's metadata, as written by `build_index.py`. */
export interface StructureMeta {
  structure_id: string
  file: string
  aa_length: number
  fused_length_expected: number
  peptide_length: number
  /** Mean pLDDT over the whole chain, normalised to 0–1. Null when the file carried none. */
  confidence: number | null
  /** Mean pLDDT over the peptide's own residues only. */
  peptide_confidence: number | null
}

interface StructureIndex {
  count: number
  missing: number
  structures: StructureMeta[]
}

/**
 * Where the bucket is.
 *
 * Read at build time from the environment and inlined by Vite, so a deployment names its
 * bucket in the build command and the value never depends on a runtime request.
 */
function structureBase(): string | null {
  const env = (import.meta as { env?: Record<string, string | undefined> }).env
  const raw = env?.VITE_STRUCTURE_BASE_URL
  if (!raw || !raw.trim()) return null
  return raw.trim().replace(/\/+$/, "")
}

/** Whether this deployment has a structure store to read from. */
export function structureEnabled(): boolean {
  return structureBase() !== null
}

let lookupPromise: Promise<Record<string, string>> | null = null
let indexPromise: Promise<StructureIndex | null> | null = null

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const response = await fetch(url, { headers: { Accept: "application/json" } })
    if (!response.ok) return null
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof Error && error.name !== "AbortError") {
      console.warn("[pepticraft] structure store unreadable:", error.message)
    }
    return null
  }
}

/** The alias table, loaded once. An empty table means the store is not reachable yet. */
export function fetchStructureLookup(): Promise<Record<string, string>> {
  const base = structureBase()
  if (!base) return Promise.resolve({})
  if (!lookupPromise) {
    lookupPromise = fetchJson<Record<string, string>>(`${base}/structure_lookup.json`).then(
      (value) => value ?? {},
    )
  }
  return lookupPromise
}

/** The metadata index, loaded once. */
export function fetchStructureIndex(): Promise<StructureIndex | null> {
  const base = structureBase()
  if (!base) return Promise.resolve(null)
  if (!indexPromise) {
    indexPromise = fetchJson<StructureIndex>(`${base}/structures.json`)
  }
  return indexPromise
}

/** The public URL of one coordinate file. */
export function structureFileUrl(structureId: string): string | null {
  const base = structureBase()
  if (!base) return null
  return `${base}/structures/${structureId}.pdb`
}

/**
 * The structure for one construct, if it has been predicted.
 *
 * The key is the same triple the builder assembles from, so a structure is found by what the
 * page is showing rather than by a separate identifier that could drift from it. A construct
 * whose scaffold or linker is not known cannot be looked up at all, and neither can one whose
 * combination was never folded.
 */
export async function findStructure(
  constructId: string,
  scaffoldId: string | null,
  linkerId: string | null,
): Promise<StructureMeta | null> {
  if (!scaffoldId || !linkerId) return null
  const [lookup, index] = await Promise.all([fetchStructureLookup(), fetchStructureIndex()])
  if (!index) return null
  const structureId = lookup[`${constructId}|${scaffoldId}|${linkerId}`]
  if (!structureId) return null
  return index.structures.find((entry) => entry.structure_id === structureId) ?? null
}
