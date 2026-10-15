/**
 * The static data source: a drop-in stand-in for the service, backed by exported JSON.
 *
 * Why this exists
 * ---------------
 * The database lives on a workstation that is not always reachable, and the Python service
 * cannot be deployed to Cloudflare Pages because `psycopg` ships a native binary. The
 * platform is therefore served as static files, and this module is what reads them.
 *
 * When it is used
 * ---------------
 * In a build served as files, and in development too. `npm run dev` sets `VITE_STATIC=1`, so
 * the export is what the frontend reads and nothing has to be running beside it; `npm run
 * dev:api` leaves the flag unset and proxies `/api` to the service, which is the mode for work
 * that has to see the database as it stands rather than as it stood when the export was made.
 * `staticEnabled()` is the gate, and `VITE_STATIC` overrides it in either direction.
 *
 * How it avoids forking the platform
 * ----------------------------------
 * The tempting version of this file re-derives composites, safety verdicts and ranking order
 * in TypeScript. That would be a mistake: every threshold, weight and verdict in this project
 * lives in the service layer, and the audit of 2026-09-17 found the same safety thresholds
 * written out four times across the frontend with one copy disagreeing with the route
 * definitions. A fifth copy would reintroduce exactly that bug class, silently, and the
 * disagreement would only surface when a construct sat on a tightened boundary.
 *
 * So this file computes nothing. It loads what `scripts/export_static.py` produced by
 * calling the service itself, and applies only the two things that are not judgement:
 *
 *   * selecting a page out of an already-ordered list, and
 *   * concatenating three already-exported amino-acid sequences into a fused one.
 *
 * Both are presentational. Neither carries a threshold, a weight or a verdict.
 *
 * What is served from where
 * -------------------------
 *   reference data, scaffolds, linkers, construct details, analysis prose
 *       static files, one request each, cached for the session
 *   construct list with filters, search, ordering and pagination
 *       the exported flat list, filtered here, because the filtering rules are substring
 *       matching and three sort keys rather than anything the database had to arbitrate
 *   the Builder's ranking
 *       the exported ranking per route and direction set, sliced here
 *   chat
 *       never static: it is a POST, and it goes to the model proxy
 *
 * Fallback
 * --------
 * If a file is missing — an export that predates a feature, or a partial export — the request
 * falls through to the service. A deployment that sets `VITE_API_BASE` therefore keeps
 * working against a live API, and one that serves only static files degrades to whatever data
 * it does have rather than to a blank page.
 */

/** Where the export lives, relative to the site root. `public/` is copied verbatim by Vite. */
function dataBase(): string {
  // `import.meta.env` is replaced at build time by Vite, and is undefined when this module is
  // loaded outside a bundle — by the static export check, or by a script that wants the same
  // lookup logic. The default is the path Vite serves `public/data` at, so both agree.
  const env = (import.meta as { env?: Record<string, string | undefined> }).env
  const raw = env?.VITE_DATA_BASE ?? "/data"
  return raw.replace(/\/+$/, "")
}

/**
 * Whether the static export may answer a request.
 *
 * The export is the only source in a build served as files, and it is the source in development
 * as well: `npm run dev` sets `VITE_STATIC=1`, so the frontend runs on its own with no service
 * beside it. `npm run dev:api` leaves the flag unset, and there the request goes over the Vite
 * proxy to the service — which is the mode to use when the answer has to reflect the database
 * as it stands rather than the snapshot an export was made from. `VITE_STATIC` overrides in
 * either direction, so a build that means to serve files from an export can say so explicitly.
 */
export function staticEnabled(): boolean {
  const env = (import.meta as { env?: Record<string, string | undefined> }).env
  // Outside a bundle there is no dev server to defer to. The export check calls `serveStatic`
  // and `applyAssemblyTargets` directly, so this answer does not affect it either way.
  if (!env) return true
  if (env.VITE_STATIC === "0") return false
  if (env.VITE_STATIC === "1") return true
  // Only a bare invocation reaches this far: an npm script has already answered above. A build
  // that names an API has a service to answer it, so the service answers. Without this rule an
  // export left in `public/data` would shadow the API on a deployment that has one — silently,
  // since the export's own `health.json` would report the result and the banner would have
  // nothing to say.
  if (env.VITE_API_BASE) return false
  return !env.DEV
}

export interface StaticManifest {
  schema_version: number
  exported_at?: string
  files: Record<string, string>
}

let manifestPromise: Promise<StaticManifest | null> | null = null
const cache = new Map<string, unknown>()

/** Load the manifest once. Absent or unreadable is not an error: it means "no static data". */
function manifest(): Promise<StaticManifest | null> {
  if (!manifestPromise) {
    manifestPromise = fetch(`${dataBase()}/manifest.json`, {
      headers: { Accept: "application/json" },
    })
      .then((r) => (r.ok ? (r.json() as Promise<StaticManifest>) : null))
      .catch((error) => {
        // A deployment with no export is an ordinary state, not a failure — the caller
        // falls back to the service. But a malformed manifest is a bug in the export, and it
        // is logged rather than swallowed so it does not present as "no static data".
        if (error instanceof Error && error.name !== "AbortError") {
          console.warn("[pepticraft] static export manifest unreadable:", error.message)
        }
        return null
      })
  }
  return manifestPromise
}

async function loadJson<T>(path: string): Promise<T | null> {
  if (cache.has(path)) return cache.get(path) as T
  const response = await fetch(`${dataBase()}/${path}`, {
    headers: { Accept: "application/json" },
  })
  if (!response.ok) return null
  const value = (await response.json()) as T
  cache.set(path, value)
  return value
}

/** One request as the static layer sees it: the method, the bare path and the query. */
export interface StaticRequest {
  method: string
  path: string
  params: URLSearchParams
}

function one(params: URLSearchParams, key: string): string | null {
  const value = params.get(key)
  return value === null || value === "" ? null : value
}

/**
 * An id written the way the exporter writes it into a filename.
 *
 * `export_static.py`'s `_safe` replaces a slash and a space with an underscore, so an id that
 * contains either is stored under a name that is not the id. The request has to apply the same
 * substitution or the lookup resolves to a file that was never written; it would then return
 * null and fall back to the service, which on a static deployment is not there.
 */
function pathSafe(identifier: string): string {
  return identifier.replace(/[/ ]/g, "_")
}

/**
 * The filename a direction set is exported under.
 *
 * The exporter writes one file per non-empty subset of the four directions, keyed by the
 * member names sorted and joined with `+`, so the key is a property of the set rather than of
 * the order it was asked for. The sort here is the default one, which orders ASCII by code
 * point on both sides — the exporter sorts the same list in Python.
 */
function directionsKey(directions: string[]): string {
  return [...new Set(directions)].sort().join("+")
}

// ── Reference ────────────────────────────────────────────────────────────────

async function meta(): Promise<Record<string, unknown> | null> {
  return loadJson("meta.json")
}

// ── Construct list ───────────────────────────────────────────────────────────
//
// The four filters the list page offers are applied here rather than in an exported file per
// combination. Four directions, two channels, four statuses and three orderings describe a few
// hundred distinct views of a list that is a few hundred rows long, so precomputing them would
// multiply the export for no gain; the rules are a substring match and three comparisons.

interface ConstructRow {
  id: string
  direction: string
  channel: string
  status: string
  rank: number | null
  peptide_sequence: string
  peptide_length: number
  // The four columns the service's `search` matches on. Three of them are provenance and are
  // null on a construct whose peptide row does not carry them; the filter below treats a null
  // as an empty column rather than as a string.
  peptide_source: string | null
  peptide_source_accession: string | null
  peptide_source_version: string | null
  [key: string]: unknown
}

/** `assembly.json`: which parts each route admits, and the notes the service writes about them. */
interface AssemblyRecipes {
  routes: Record<
    string,
    {
      scaffolds: string[]
      linkers: string[]
      binding_note: string
      linker_note: string
      scope_note: string
    }
  >
}

let allRows: ConstructRow[] | null = null
let compositeTable: Record<string, Record<string, number | null>> | null = null
let verdictTable: Record<string, Record<string, string>> | null = null
let routeTablesPromise: Promise<void> | null = null

/**
 * Load the per-route composite and verdict tables, once, whoever asks first.
 *
 * A detail page can be the first request in a session — a shared link to one construct — so
 * these cannot be a side effect of loading the list, or a route switch on a directly-linked
 * page would silently keep the default route's composite and verdict.
 */
function ensureRouteTables(): Promise<void> {
  if (!routeTablesPromise) {
    routeTablesPromise = (async () => {
      compositeTable = await loadJson("composites.json")
      verdictTable = await loadJson("verdicts.json")
    })()
  }
  return routeTablesPromise
}

/**
 * The composite under each route, substituted into a summary row.
 *
 * The exported summary carries the composite for the first declared route, because that is
 * what the service produces when no route is named. The list page lets the reader switch
 * routes, and the composite and the safety verdict both move when they do — the
 * immunogenicity gate is the route's threshold — so those two fields are read from the
 * per-route tables rather than left at their defaults.
 */
function applyRoute(row: ConstructRow, routeId: string | null): Record<string, unknown> {
  if (!routeId) return row as unknown as Record<string, unknown>
  const composite = compositeTable?.[row.id]?.[routeId]
  const verdict = verdictTable?.[row.id]?.[routeId]
  if (composite === undefined && verdict === undefined) {
    return row as unknown as Record<string, unknown>
  }
  return {
    ...row,
    composite: composite === undefined ? row.composite : composite,
    safety_verdict: verdict ?? row.safety_verdict,
  }
}

async function constructList(params: URLSearchParams): Promise<unknown | null> {
  if (allRows === null) {
    const payload = await loadJson<{ items: ConstructRow[] }>("constructs.json")
    if (!payload) return null
    allRows = payload.items
    // The two per-route tables are optional: an export without them still lists constructs,
    // just with the composite pinned to the default route.
    await ensureRouteTables()
  }

  const direction = one(params, "direction")
  const channel = one(params, "channel")
  const status = one(params, "status")
  // Trimmed like the service's own router, which strips the term before it reaches the query.
  const search = one(params, "search")?.trim().toLowerCase() || null
  const order = one(params, "order") ?? "rank"
  const limit = Number(one(params, "limit") ?? 50)
  const offset = Number(one(params, "offset") ?? 0)
  const routeId = one(params, "route_id")

  let rows = allRows
  if (direction) rows = rows.filter((r) => r.direction === direction)
  if (channel) rows = rows.filter((r) => r.channel === channel)
  if (status) rows = rows.filter((r) => r.status === status)
  if (search) {
    rows = rows.filter((r) => {
      // The four columns the service searches, each matched on its own — the service writes
      // `lower(col) LIKE ...` four times and ORs the results, so this is the same predicate.
      // The columns were previously joined into one string, which had two faults: a column the
      // export did not carry rendered as the literal text "undefined", so searching for that
      // word returned every row, and the three provenance columns could not match at all
      // because the exported row did not hold them. They are on the row now.
      //
      // A null is an empty column, not the string "null". The term is a literal substring:
      // `%` and `_` match themselves, which is what the service's escape does there.
      const columns = [
        r.peptide_sequence,
        r.peptide_source,
        r.peptide_source_accession,
        r.peptide_source_version,
      ]
      return columns.some((column) => (column ?? "").toLowerCase().includes(search))
    })
  }

  const sorted = [...rows]
  if (order === "peptide_length") {
    sorted.sort((a, b) => a.peptide_length - b.peptide_length || a.id.localeCompare(b.id))
  } else if (order === "peptide_id") {
    sorted.sort((a, b) => a.id.localeCompare(b.id))
  } else {
    // The pipeline's own ordering within each direction and channel: rank ascending, with the
    // rows that carry no rank after the ones that do, and the id as the final tiebreak so two
    // requests over the same data cannot disagree about the order.
    sorted.sort((a, b) => {
      const ra = a.rank ?? Number.MAX_SAFE_INTEGER
      const rb = b.rank ?? Number.MAX_SAFE_INTEGER
      return ra - rb || a.id.localeCompare(b.id)
    })
  }

  return {
    items: sorted.slice(offset, offset + limit).map((r) => applyRoute(r, routeId)),
    total: sorted.length,
    limit,
    offset,
  }
}

// ── Builder ──────────────────────────────────────────────────────────────────

/**
 * A stored ranking, sliced to the requested page.
 *
 * The exported ranking is already ordered by the service under the route's weighting profile,
 * over the whole candidate set. `counts` therefore describes the entire candidate set rather
 * than the returned page, which is the distinction the contract draws and the reason the tally
 * is copied rather than recomputed here.
 *
 * One file per direction set, not one per route. The service ranks a set as a set — the order
 * depends on every member, through the route's weights — so a two-direction request cannot be
 * answered by slicing a four-direction file, and merging the single-direction files here would
 * put the ordering rule in TypeScript. The exporter writes every subset for that reason.
 */
async function build(params: URLSearchParams): Promise<unknown | null> {
  const routeId = one(params, "route_id")
  const directions = params.getAll("direction").flatMap((d) => d.split(",")).filter(Boolean)
  if (!routeId || directions.length === 0) return null

  const result = await loadJson<Record<string, unknown>>(
    `builds/${pathSafe(routeId)}/${pathSafe(directionsKey(directions))}.json`,
  )
  if (!result) return null

  const limit = Number(one(params, "limit") ?? 50)
  const offset = Number(one(params, "offset") ?? 0)
  const items = (result.items as unknown[]) ?? []
  const page = items.slice(offset, offset + limit)

  // The reader's pairing, when they chose one. The ranking itself is the service's and is used
  // as stored; only the sequences are assembled here, and `counts` still describes the whole
  // candidate set rather than the page.
  const scaffoldId = one(params, "scaffold_id")
  const linkerId = one(params, "linker_id")
  if (!scaffoldId && !linkerId) {
    return { ...result, directions, items: page, limit, offset }
  }

  const recipes = await loadJson<AssemblyRecipes>("assembly.json")
  const routeRecipes = recipes?.routes?.[routeId]

  // Resolved once, not per row. Naming a scaffold or a linker is a decision about the whole
  // build — every candidate is assembled from the same two parts — and the service reports the
  // named pair in the same places: the top-level `scaffold` and `linker`, and each row's
  // `linker_name`. A linker named without a scaffold still reaches the rows, which a build that
  // only looked at the assembled result would drop.
  const [scaffoldView, linkerView] = await Promise.all([
    namedScaffold(scaffoldId),
    namedLinkerView(linkerId),
  ])
  const assembled = await Promise.all(
    page.map(async (item) => {
      const id = String((item as { id: string }).id)
      const built = await assemble(id, scaffoldId, linkerId)
      if (!built) {
        return linkerView
          ? { ...(item as Record<string, unknown>), linker_name: linkerView.name }
          : item
      }
      return {
        ...(item as Record<string, unknown>),
        backbone_id: scaffoldId ?? (item as Record<string, unknown>).backbone_id,
        // The scaffold's own short name, which is what the service puts in this field when it
        // assembles a request-time scaffold — not the id, which is what the identifier is for.
        backbone_name: built.name,
        backbone_binding: "inferred",
        full_sequence: built.sequence,
        fused_length: built.sequence.length,
        assembled_sequence_available: true,
        segments: built.segments,
        linker_name: built.linkerName ?? (item as Record<string, unknown>).linker_name,
      }
    }),
  )

  return {
    ...result,
    directions,
    items: assembled,
    limit,
    offset,
    scaffold_id: scaffoldId,
    linker_id: linkerId,
    scaffold: scaffoldView,
    linker: linkerView,
    binding_note: routeRecipes?.binding_note ?? result.binding_note,
    linker_note: routeRecipes?.linker_note ?? result.linker_note,
    scope_note: routeRecipes?.scope_note ?? result.scope_note,
  }
}

/**
 * The two embedded objects the service sends beside the fused sequence.
 *
 * A construct response carries more than a sequence and two display names. It carries the
 * `scaffold` summary and the `linker` view themselves, and the pages read those: the heading
 * prints `scaffold.short_name`, the summary card prints it again and takes the linker's name
 * from `linker.name`, the eligible-scaffold list highlights the entry whose id equals
 * `scaffold.id`, and the linker tab is rendered from `linker` alone. Emitting only the names
 * and the segments — which is what this module did — left every one of those reading a null,
 * so a page showed `scaffold unassigned` and the stored linker directly above a fused sequence
 * that had just been assembled from the scaffold and linker the reader picked.
 *
 * Both are projected rather than passed through, so the static shapes match the service's. The
 * exported scaffold file is the cluster *detail* (it also carries `description`, `sequences`,
 * `experiments` and the fields the dataset does not have), and the exported linker file is the
 * linker *detail*; the service embeds the summary and the list view in these positions.
 */

interface ExportedScaffold {
  id: string
  name: string
  short_name: string
  category?: string | null
  applicant?: string
  patent?: string | null
  length?: number | null
  species?: string | null
  sequence_count?: number
  application_tags?: string[]
  route_ids?: string[]
  material_forms?: string[]
  max_evidence?: string | null
  has_sequence?: boolean
  sequences?: { sequence?: string }[]
}

interface ExportedLinker {
  id: string
  name: string
  sequence: string
  length: number
  rigidity: string
  source_table: string
  unit_composition?: unknown[]
  description?: string | null
  reference?: string | null
  priority_rank?: number | null
  priority_reason?: string | null
}

function scaffoldSummary(file: ExportedScaffold): Record<string, unknown> {
  return {
    id: file.id,
    name: file.name,
    short_name: file.short_name,
    category: file.category ?? null,
    applicant: file.applicant ?? "",
    patent: file.patent ?? null,
    length: file.length ?? null,
    species: file.species ?? null,
    sequence_count: file.sequence_count ?? 0,
    application_tags: file.application_tags ?? [],
    route_ids: file.route_ids ?? [],
    material_forms: file.material_forms ?? [],
    max_evidence: file.max_evidence ?? null,
    has_sequence: file.has_sequence ?? false,
  }
}

function linkerPreview(file: ExportedLinker): Record<string, unknown> {
  return {
    id: file.id,
    name: file.name,
    sequence: file.sequence,
    length: file.length,
    rigidity: file.rigidity,
    source_table: file.source_table,
    unit_composition: file.unit_composition ?? [],
    description: file.description ?? null,
    reference: file.reference ?? null,
    priority_rank: file.priority_rank ?? null,
    priority_reason: file.priority_reason ?? null,
  }
}

/**
 * A named scaffold, as the summary the service embeds. Independent of assembly, because the
 * build response carries the named scaffold at its top level whether or not a fused sequence
 * could be emitted from it.
 */
async function namedScaffold(scaffoldId: string | null): Promise<Record<string, unknown> | null> {
  if (!scaffoldId) return null
  const file = await loadJson<ExportedScaffold>(`scaffolds/${pathSafe(scaffoldId)}.json`)
  return file ? scaffoldSummary(file) : null
}

/**
 * A named linker's exported file.
 *
 * The curated library is what the interface offers, and the export writes one file per entry,
 * so this resolves every id a reader can name through the interface. The six sample rows are
 * not exported under `linkers/`: an id from that table that arrives by hand resolves to
 * nothing and the caller keeps what the row already carries, rather than being handed a linker
 * this deployment cannot describe.
 */
async function namedLinkerFile(linkerId: string | null): Promise<ExportedLinker | null> {
  if (!linkerId) return null
  return loadJson<ExportedLinker>(`linkers/${pathSafe(linkerId)}.json`)
}

/** The same file, projected onto the view the service embeds in a response. */
async function namedLinkerView(linkerId: string | null): Promise<Record<string, unknown> | null> {
  const file = await namedLinkerFile(linkerId)
  return file ? linkerPreview(file) : null
}

/**
 * The fused sequence for one candidate under one pairing.
 *
 * The only computation this module performs, and it is string joining. `assembly.json` names
 * which scaffolds and linkers each route admits and carries one worked example produced by the
 * service itself; the sequences themselves come from the scaffold and linker files. The
 * provenance is unchanged from what the service reports: a pairing named by the reader is a
 * reconstruction, reported as `inferred`, and never as a pipeline result.
 *
 * The scaffold, the linker and the peptide are resolved and reported together here, because a
 * response that named the parts in one place and assembled them in another is what let the
 * page disagree with itself.
 */
interface Assembly {
  sequence: string
  name: string
  linkerName: string | null
  segments: unknown[]
  scaffold: Record<string, unknown>
  linker: Record<string, unknown> | null
}

async function assemble(
  constructId: string,
  scaffoldId: string | null,
  linkerId: string | null,
): Promise<Assembly | null> {
  if (!scaffoldId) return null
  const scaffold = await loadJson<ExportedScaffold>(`scaffolds/${pathSafe(scaffoldId)}.json`)
  if (!scaffold?.sequences?.length) return null

  // The longest variant is the representative one, which is the same rule the service applies
  // when it resolves a cluster to a single sequence.
  const backbone = scaffold.sequences
    .map((s) => s.sequence ?? "")
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)[0]
  if (!backbone) return null

  const [construct, chosen] = await Promise.all([
    loadJson<{ peptide_sequence: string; linker?: ExportedLinker | null }>(
      `constructs/${constructId}.json`,
    ),
    namedLinkerFile(linkerId),
  ])
  const peptide = construct?.peptide_sequence ?? ""

  // Which linker is in the middle. The service's rule, from `assemble_row`: the one the request
  // named, or — when it named none — the one the construct's own row records. A detail page can
  // be opened as `?scaffold_id=…` with no linker, and this is not a labelling detail: the
  // stored linker's residues sit between the scaffold and the peptide, so dropping it emits a
  // fusion several residues shorter than the service's and the same URL shows two different
  // sequences on the two deployments.
  const stored = (construct?.linker ?? null) as ExportedLinker | null
  const linker = chosen ?? stored
  const middle = linker?.sequence ?? ""
  const sequence = `${backbone}${middle}${peptide}`

  // The names, not the identifiers. The service resolves a request-time scaffold to its
  // `short_name` and a linker to its `name`, and puts those in `backbone_name`, `linker_name`
  // and the segment labels; the pages print `backbone_name` straight into a heading, so a
  // reader on a static deployment would otherwise be shown `fixture-silk-s1` where the
  // development build shows `Fixture S1`.
  const name = scaffold.short_name || scaffold.name || scaffoldId
  const linkerName = linker ? linker.name || linkerId || "" : null

  return {
    sequence,
    name,
    linkerName,
    scaffold: scaffoldSummary(scaffold),
    linker: linker ? linkerPreview(linker) : null,
    segments: [
      {
        label: `Backbone: ${name}`,
        sequence: backbone,
        color: "backbone",
        type: "backbone",
        available: true,
      },
      {
        // The service's two states: a linker it resolved, or the stand-in it writes when the
        // sequence could not be resolved at all.
        label: linker ? `Linker: ${linkerName}` : "Linker: sequence unavailable",
        sequence: middle,
        color: "linker",
        type: "linker",
        available: Boolean(middle),
      },
      {
        label: "Peptide",
        sequence: peptide,
        color: "peptide",
        type: "peptide",
        available: Boolean(peptide),
      },
    ],
  }
}

// ── Dispatch ─────────────────────────────────────────────────────────────────

interface Handled {
  payload: unknown
  /**
   * Set on a branch whose path is keyed by an identifier, where an empty payload means "this
   * record is not in the export" rather than "this export does not answer this path".
   *
   * The two are different answers and the caller acts on them differently: the first is a
   * not-found, the second is a fall-through to the service. Without the distinction both arrive
   * as `null` and the caller sends a missing record to a service that, in a static deployment,
   * is not there — the request then reaches the SPA fallback and the reader is told the
   * response was malformed instead of that the record does not exist.
   */
  keyed?: boolean
}

async function handle(request: StaticRequest): Promise<Handled | null> {
  const { method, path, params } = request

  // Health. Served from the export's own record rather than probed, because a static
  // deployment has no database that could be unreachable and reporting otherwise would put a
  // false failure on every page load.
  if (path === "/api/health" && method === "GET") {
    return { payload: await loadJson("health.json") }
  }

  if (method === "GET") {
    if (path === "/api/meta/reference") {
      const bundle = await meta()
      return bundle ? { payload: bundle } : null
    }
    if (path === "/api/meta/directions") return { payload: await loadJson("meta/directions.json") }
    if (path === "/api/meta/routes") return { payload: await loadJson("meta/routes.json") }
    if (path === "/api/meta/tools") return { payload: await loadJson("meta/tools.json") }
    if (path === "/api/meta/pipeline") return { payload: await loadJson("meta/pipeline.json") }
    // Exported because the service exposes it. No page calls it yet; the branch exists so the
    // export and the service cover the same set of paths, which is what the check script
    // asserts and what keeps a page written against this endpoint from working in development
    // and returning nothing in the deployment.
    if (path === "/api/meta/coverage") return { payload: await loadJson("meta/coverage.json") }
    if (path === "/api/scaffolds") {
      const routeId = one(params, "route_id")
      const file = routeId
        ? `scaffolds/route/${pathSafe(routeId)}.json`
        : "scaffolds.json"
      return { payload: await loadJson(file) }
    }
    if (path === "/api/linkers") {
      const include = one(params, "include_placeholder") === "true"
      return { payload: await loadJson(include ? "linkers/all.json" : "linkers.json") }
    }
    if (path === "/api/constructs") {
      return { payload: await constructList(params) }
    }
    if (path === "/api/build") {
      return { payload: await build(params) }
    }

    // /api/constructs/{id}
    const detail = /^\/api\/constructs\/(con_\d+)$/.exec(path)
    if (detail) {
      const id = detail[1]
      const loaded = await loadJson<Record<string, unknown>>(`constructs/${id}.json`)
      if (!loaded) return { payload: null, keyed: true }

      // The detail's own `composite` and `safety` follow the first declared route. When the
      // page asks for another, both are replaced from the per-route tables so the numbers on
      // the page and the route shown beside them cannot disagree.
      let payload = loaded
      const routeId = one(params, "route_id")
      if (routeId) {
        await ensureRouteTables()
        const composite = compositeTable?.[id]?.[routeId]
        const verdict = verdictTable?.[id]?.[routeId]
        if (composite !== undefined || verdict !== undefined) {
          const scores = (loaded.scores ?? {}) as Record<string, unknown>
          // The two tables are written by different loops — the composite only for a route the
          // service computed one under, the verdict for every route — so one can name a route
          // the other does not. Each field falls back on its own: a route with a new verdict and
          // no new composite keeps the composite it already had, at the top level and inside
          // `scores`, rather than having the latter overwritten with `undefined`.
          const shownComposite = composite === undefined ? scores.composite ?? null : composite
          payload = {
            ...loaded,
            composite: shownComposite,
            safety_verdict: verdict ?? loaded.safety_verdict,
            scores: { ...scores, composite: shownComposite },
          }
        }
      }

      // A reader who named a scaffold or a linker gets the fused sequence assembled from the
      // exported parts, which is the only thing this module computes. Doing it here rather
      // than in the caller keeps it on the static path: a response that came from the service
      // has already been assembled by the service, and must not be overwritten by a file.
      const scaffoldId = one(params, "scaffold_id")
      const linkerId = one(params, "linker_id")
      if (scaffoldId || linkerId) {
        payload = await applyAssemblyTargets(payload, scaffoldId, linkerId)
      }

      return { payload }
    }

    const scaffoldsFor = /^\/api\/constructs\/(con_\d+)\/scaffolds$/.exec(path)
    if (scaffoldsFor) {
      return {
        payload: await loadJson(`constructs/${scaffoldsFor[1]}/scaffolds.json`),
        keyed: true,
      }
    }

    const analysis = /^\/api\/constructs\/(con_\d+)\/analysis$/.exec(path)
    if (analysis) {
      // One prose export per construct. The safety paragraph is the only block whose wording
      // moves with the route, and the route-specific verdict and threshold travel separately in
      // `verdicts.json` and in the detail's own `safety`, so a reader on a non-default route
      // sees the same six paragraphs with the right verdict already substituted on the page.
      return {
        payload: await loadJson(`constructs/${analysis[1]}/analysis.json`),
        keyed: true,
      }
    }

    const peptide = /^\/api\/constructs\/(con_\d+)\/peptide$/.exec(path)
    if (peptide) {
      const table = await loadJson<Record<string, unknown>>("peptide_details.json")
      return { payload: table?.[peptide[1]] ?? null, keyed: true }
    }

    const scaffold = /^\/api\/scaffolds\/(.+)$/.exec(path)
    if (scaffold) {
      return { payload: await loadJson(`scaffolds/${pathSafe(scaffold[1])}.json`), keyed: true }
    }

    const linker = /^\/api\/linkers\/(.+)$/.exec(path)
    if (linker) {
      return { payload: await loadJson(`linkers/${pathSafe(linker[1])}.json`), keyed: true }
    }
  }

  return null
}

/**
 * What the export can say about a request.
 *
 * Three answers rather than two, because "this export does not answer this path" and "this
 * export answered, and the record is not in it" are acted on differently: the first falls
 * through to the service, the second is a not-found. A single nullable payload cannot tell
 * them apart, and a caller that conflates them sends a missing record to a service that a
 * static deployment does not have — where the request reaches the SPA fallback and the reader
 * is told the response was malformed rather than that the record does not exist.
 */
export interface StaticResult {
  /** Whether this export is the authority for the path. */
  covered: boolean
  /** What it holds. Null on a covered path means the record is not in the export. */
  payload: unknown
}

export async function serveStaticResult(
  method: string,
  path: string,
  params: URLSearchParams,
): Promise<StaticResult> {
  try {
    const handled = await handle({ method, path, params })
    if (handled === null) return { covered: false, payload: null }
    if (handled.payload !== null && handled.payload !== undefined) {
      return { covered: true, payload: handled.payload }
    }
    // Empty. On a branch keyed by an identifier the export is still the authority and the
    // record simply is not in it; anywhere else an empty result means the export has nothing
    // to say about this call, which is the ordinary fall-through.
    return { covered: handled.keyed === true, payload: null }
  } catch {
    // A malformed or truncated export must not take the page down; the caller falls back to
    // the service, and if there is none the page reports an ordinary fetch failure.
    return { covered: false, payload: null }
  }
}

/**
 * The payload, or null to let the caller fall back.
 *
 * The three-state answer read one way, for callers that want only the data — the check script
 * drives every path through it. A POST is never served, and neither is a path the export does
 * not cover.
 */
export async function serveStatic(
  method: string,
  path: string,
  params: URLSearchParams,
): Promise<unknown | null> {
  const result = await serveStaticResult(method, path, params)
  return result.covered ? result.payload : null
}

/**
 * Apply a reader's scaffold and linker choice to a construct detail.
 *
 * Mirrors what the service does with `?scaffold=` and `?linker_id=`: the scaffold named by the
 * reader wins over the stored binding and is reported as `inferred`, because the row does not
 * record that pairing. With neither named, the stored binding stands — a real scaffold on a
 * backfilled row, a marker string on one that is still a placeholder, in which case no
 * sequence is emitted and the interface shows the segments it has without inventing the one
 * it does not.
 */
export async function applyAssemblyTargets(
  detail: Record<string, unknown>,
  scaffoldId: string | null,
  linkerId: string | null,
): Promise<Record<string, unknown>> {
  if (!scaffoldId && !linkerId) return detail
  const id = String(detail.id)

  // The scaffold and the linker are resolved independently, which is what the service does. A
  // request that names only a linker still has that linker reported against the record, and a
  // request that names only a scaffold keeps the linker the construct's own row records — the
  // rows are what carry it, and the response has to say which of the two happened.
  const [assembled, linkerView] = await Promise.all([
    scaffoldId ? assemble(id, scaffoldId, linkerId) : Promise.resolve(null),
    namedLinkerView(linkerId),
  ])
  if (!assembled && !linkerView) return detail

  return {
    ...detail,
    ...(linkerView && !assembled ? { linker: linkerView } : {}),
    ...(assembled
      ? {
          backbone_id: scaffoldId,
          // The scaffold's short name, as the service writes it for a request-time scaffold. The
          // id is already in `backbone_id`; putting it here as well made the page print an
          // identifier where the development build prints a name.
          backbone_name: assembled.name,
          backbone_binding: "inferred",
          backbone_binding_note:
            "The scaffold was named at request time rather than read from the stored construct. " +
            "The fused sequence uses that scaffold's real sequence, so it is a faithful assembly " +
            "of a real scaffold with a real linker and peptide, but the scaffold-to-construct " +
            "assignment is a reconstruction and not a pipeline output.",
          full_sequence: assembled.sequence,
          assembled_sequence_available: true,
          segments: assembled.segments,
          // The two objects every surface reads. `linker` here is the one the sequence in
          // `full_sequence` was actually built with — the named one, or the stored one when the
          // request named none.
          scaffold: assembled.scaffold,
          linker: assembled.linker,
          linker_name: assembled.linkerName ?? detail.linker_name,
        }
      : {}),
  }
}

/** Whether an export is present, for the data-source banner and for the build's own checks. */
export async function staticAvailable(): Promise<boolean> {
  return (await manifest()) !== null
}