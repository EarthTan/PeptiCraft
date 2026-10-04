/**
 * Endpoint bindings, one function per route the service exposes.
 *
 * Nothing here transforms a response. That is the point: if a page needs a number reformatted
 * or a threshold re-derived, the change belongs in the service, not in a client-side helper
 * that would become a second place the rule lives.
 */
import { postJson, request } from "./client"
import type {
  AnalysisResponse,
  BuildResult,
  ChatMessage,
  ChatResponse,
  ConstructDetail,
  ConstructSummary,
  DeliveryRoute,
  FunctionDirection,
  HealthResponse,
  LinkerDetail,
  LinkerView,
  Paginated,
  PipelineView,
  ReferenceData,
  ScaffoldDetail,
  ScaffoldSummary,
  ToolDefinition,
} from "./types"

type QueryValue = string | number | boolean | null | undefined

function queryString(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue
    search.set(key, String(value))
  }
  const rendered = search.toString()
  return rendered ? `?${rendered}` : ""
}

// ── Health ──────────────────────────────────────────────────────────────────

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health")
}

// ── Reference data ──────────────────────────────────────────────────────────
//
// `fetchReference` bundles directions, routes, tools, evidence levels, material forms and
// scaffold categories into one response. The Builder cannot render its first step without
// all of it, so splitting it into four calls would cost four round trips on first paint to
// save nothing.

export function fetchReference(): Promise<ReferenceData> {
  return request<ReferenceData>("/api/meta/reference")
}

export function fetchDirections(): Promise<FunctionDirection[]> {
  return request<FunctionDirection[]>("/api/meta/directions")
}

export function fetchRoutes(): Promise<DeliveryRoute[]> {
  return request<DeliveryRoute[]>("/api/meta/routes")
}

export function fetchTools(): Promise<ToolDefinition[]> {
  return request<ToolDefinition[]>("/api/meta/tools")
}

export function fetchPipeline(): Promise<PipelineView> {
  return request<PipelineView>("/api/meta/pipeline")
}

// ── Constructs ──────────────────────────────────────────────────────────────

export interface ConstructQuery {
  direction?: string | null
  channel?: "top" | "bottom" | null
  status?: "passed" | "failed_safety" | "failed_score" | "WIP" | null
  /** Application route whose screening profile the composite and safety verdict use. */
  route_id?: string | null
  limit?: number
  offset?: number
}

export function fetchConstructs(query: ConstructQuery = {}): Promise<Paginated<ConstructSummary>> {
  return request<Paginated<ConstructSummary>>(`/api/constructs${queryString({ ...query })}`)
}

export function fetchConstruct(
  id: string,
  options: {
    route_id?: string | null
    scaffold_id?: string | null
    linker_id?: string | null
  } = {},
): Promise<ConstructDetail> {
  return request<ConstructDetail>(`/api/constructs/${id}${queryString({ ...options })}`)
}

/** Scaffolds that could assemble this construct. Offered as options, never applied silently. */
export function fetchConstructScaffolds(id: string): Promise<ScaffoldSummary[]> {
  return request<ScaffoldSummary[]>(`/api/constructs/${id}/scaffolds`)
}

export function fetchConstructAnalysis(
  id: string,
  route_id?: string | null,
): Promise<AnalysisResponse> {
  return request<AnalysisResponse>(
    `/api/constructs/${id}/analysis${queryString({ route_id })}`,
  )
}

export interface ChatRequestPayload {
  message: string
  route_id?: string | null
  history?: ChatMessage[]
}

export function sendChat(id: string, payload: ChatRequestPayload): Promise<ChatResponse> {
  return postJson<ChatResponse>(`/api/constructs/${id}/chat`, {
    construct_id: id,
    message: payload.message,
    route_id: payload.route_id ?? null,
    history: payload.history ?? [],
  })
}

// ── Build ───────────────────────────────────────────────────────────────────

export interface BuildQuery {
  /** One or more function directions. Sent as a repeated parameter, which is what the
   *  service reads — see `fetchBuild`. */
  direction: string[]
  route_id?: string | null
  /** The scaffold every candidate is assembled against. When omitted, each row inherits its
   *  own stored binding and the rows can disagree with one another. */
  scaffold_id?: string | null
  /** The linker every candidate is assembled with. When omitted, each row keeps the linker
   *  its own stored row records. Unlike the scaffold, this is not narrowed by the route:
   *  the library is short and the same for every route. */
  linker_id?: string | null
  limit?: number
  offset?: number
}

/** Rank the candidates for a route, a scaffold and a linker, assembling each candidate's
 *  fused sequence.
 *
 *  This is the Builder's own step: not a query over stored constructs but a composition of
 *  them, so it is the one call that returns a fused sequence per candidate. The directions go
 *  out as a repeated parameter rather than a joined string, because a direction id is
 *  free-form text and any separator the ids could contain would merge two requests into one.
 */
export function fetchBuild(query: BuildQuery): Promise<BuildResult> {
  const search = new URLSearchParams()
  for (const direction of query.direction) search.append("direction", direction)
  for (const [key, value] of Object.entries({
    route_id: query.route_id,
    scaffold_id: query.scaffold_id,
    linker_id: query.linker_id,
    limit: query.limit,
    offset: query.offset,
  })) {
    if (value === null || value === undefined || value === "") continue
    search.set(key, String(value))
  }
  return request<BuildResult>(`/api/build?${search.toString()}`)
}

// ── Scaffolds ───────────────────────────────────────────────────────────────

export function fetchScaffolds(
  options: { route_id?: string | null; category?: string | null } = {},
): Promise<ScaffoldSummary[]> {
  return request<ScaffoldSummary[]>(`/api/scaffolds${queryString({ ...options })}`)
}

export function fetchScaffold(id: string): Promise<ScaffoldDetail> {
  return request<ScaffoldDetail>(`/api/scaffolds/${encodeURIComponent(id)}`)
}

// ── Linkers ─────────────────────────────────────────────────────────────────

export function fetchLinkers(include_placeholder = false): Promise<LinkerView[]> {
  return request<LinkerView[]>(
    `/api/linkers${queryString({ include_placeholder })}`,
  )
}

export function fetchLinker(id: string): Promise<LinkerDetail> {
  return request<LinkerDetail>(`/api/linkers/${encodeURIComponent(id)}`)
}
