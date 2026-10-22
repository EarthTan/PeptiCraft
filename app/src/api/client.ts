/**
 * The single HTTP entry point for the platform.
 *
 * Every request goes through `request()`, which normalises four different failure modes into
 * one `ApiError` so a page never has to guess what went wrong. The distinction matters here
 * because the database lives on a separate host reached over its IP: "the service is not
 * running", "the service is running but cannot reach the database" and "the query failed"
 * look identical to a user unless the layer between them keeps them apart.
 *
 * Base URL. In development the base is empty and `/api` is forwarded to the service by the
 * Vite proxy, which keeps the browser on one origin and avoids any CORS configuration during
 * development. A deployment that serves the built assets from a different host than the API
 * sets `VITE_API_BASE` to the service's origin at build time.
 *
 * Static first. The platform is served as files in production and, by default, in development
 * too: `npm run dev` sets `VITE_STATIC=1`, so the export answers before anything goes out and
 * the frontend runs with no service started beside it. `npm run dev:api` leaves the flag unset
 * and goes to the service instead, which is the mode for work that has to see current data —
 * a static read shows the snapshot the export was made from, not the database as it stands.
 *
 * The lookup happens before the request so the two paths cannot disagree about a shape — they
 * are the same functions' output, one read from a file. A GET that the export does not cover
 * falls through to the network. The exchange is one-way on purpose: a request the export
 * *does* cover is answered from the file and never reaches the service.
 *
 * A covered path whose record is missing is the one case that does not fall through. Falling
 * through would send it to a service that a static deployment does not have, and the request
 * would land on the SPA fallback and come back as HTML — reported to the reader as a malformed
 * response instead of as a missing record. The export is the authority for the paths it holds,
 * absence included, so this raises `not_found` directly.
 */

import { serveStaticResult, staticAvailable, staticEnabled } from "./static"

export type ApiErrorKind =
  | "network"
  | "database_unavailable"
  | "data_unavailable"
  | "llm_not_configured"
  | "model_unavailable"
  | "invalid_model_output"
  | "not_found"
  | "bad_request"
  | "server"
  | "invalid_response"

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | null
  readonly detail: string | null
  readonly hint: string | null

  constructor(
    kind: ApiErrorKind,
    message: string,
    options: { status?: number | null; detail?: string | null; hint?: string | null } = {},
  ) {
    super(message)
    this.name = "ApiError"
    this.kind = kind
    this.status = options.status ?? null
    this.detail = options.detail ?? null
    this.hint = options.hint ?? null
  }
}

export function apiBase(): string {
  // `import.meta.env` is replaced at build time by Vite and is undefined when this module is
  // loaded outside a bundle, which the static export check does. An empty base is the right
  // answer in both cases: it means "same origin".
  const env = (import.meta as { env?: Record<string, string | undefined> }).env
  const raw = env?.VITE_API_BASE
  if (!raw) return ""
  return raw.replace(/\/+$/, "")
}

interface ErrorBody {
  error?: string
  detail?: string
  hint?: string
}

async function readErrorBody(response: Response): Promise<ErrorBody> {
  try {
    const parsed = (await response.json()) as unknown
    if (parsed && typeof parsed === "object") return parsed as ErrorBody
    return {}
  } catch {
    return {}
  }
}

function classify(status: number, body: ErrorBody): ApiErrorKind {
  if (body.error === "llm_not_configured") return "llm_not_configured"
  if (body.error === "model_unavailable") return "model_unavailable"
  if (body.error === "invalid_model_output") return "invalid_model_output"
  if (body.error === "data_unavailable") return "data_unavailable"
  if (body.error === "database_unavailable") return "database_unavailable"
  if (status === 404) return "not_found"
  if (status === 400 || status === 422) return "bad_request"
  if (status === 503) return "database_unavailable"
  return "server"
}

/** Split a path into its segments-free form and its query, so the static layer can read both. */
function splitPath(path: string): { bare: string; params: URLSearchParams } {
  const mark = path.indexOf("?")
  if (mark === -1) return { bare: path, params: new URLSearchParams() }
  return {
    bare: path.slice(0, mark),
    params: new URLSearchParams(path.slice(mark + 1)),
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase()

  // Static first, in a build that has no service. A path the export does not cover falls
  // through, which is the normal answer for the chat POST and for any endpoint added after the
  // export was made. A path it does cover is answered here either way — with the record, or
  // with a not-found when the record is not in the snapshot.
  if (method === "GET" && staticEnabled()) {
    const { bare, params } = splitPath(path)
    const served = await serveStaticResult(method, bare, params)
    if (served.covered) {
      if (served.error) {
        throw new ApiError(served.error.kind, served.error.detail, {
          status: 503, detail: served.error.detail, hint: served.error.hint,
        })
      }
      if (served.payload === null || served.payload === undefined) {
        throw new ApiError("not_found", "This record is not in the deployment's dataset.", {
          detail: bare,
          hint:
            "This deployment serves a snapshot exported from the database at a point in time. " +
            "The record may have been added after that export, or removed from the database " +
            "since. Re-running the export refreshes it.",
        })
      }
      return served.payload as T
    }
  }

  const url = `${apiBase()}${path}`
  let response: Response
  try {
    response = await fetch(url, {
      headers: { Accept: "application/json" },
      ...init,
    })
  } catch (cause) {
    // In static mode a failed request usually means the export is not there at all: the call
    // fell through every path the export could have answered and reached a service this mode
    // does not start. Telling the reader to start the service would send them after the one
    // thing the mode exists to avoid, so the two situations get different sentences.
    const noExport = staticEnabled() && !(await staticAvailable())
    throw new ApiError("network", "The API could not be reached.", {
      detail: cause instanceof Error ? cause.message : String(cause),
      hint: noExport
        ? "This frontend reads a static export and there is none under public/data. Produce " +
          "one by running scripts/export_static.py in service/ (add --allow-fixture for a " +
          "local export before the database is reachable), or run against the service " +
          "instead with `npm run dev:api`."
        : "Start the service (uvicorn app.main:app) and confirm the Vite dev server is " +
          "proxying /api to it.",
    })
  }

  if (!response.ok) {
    const body = await readErrorBody(response)
    throw new ApiError(
      classify(response.status, body),
      body.detail ?? `${response.status} ${response.statusText}`,
      { status: response.status, detail: body.detail ?? null, hint: body.hint ?? null },
    )
  }

  try {
    return (await response.json()) as T
  } catch (cause) {
    throw new ApiError("invalid_response", "The API returned a body that is not JSON.", {
      status: response.status,
      detail: cause instanceof Error ? cause.message : String(cause),
    })
  }
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  })
}

/** Short heading for an error state, phrased as the condition rather than as a fault. */
export function errorTitle(error: ApiError): string {
  switch (error.kind) {
    case "network":
      return "Service unreachable"
    case "database_unavailable":
      return "Database unreachable"
    case "data_unavailable":
      return "Dataset unavailable"
    case "llm_not_configured":
      return "AI model not configured"
    case "model_unavailable":
      return "AI model unavailable"
    case "invalid_model_output":
      return "AI answer could not be verified"
    case "not_found":
      return "Not found"
    case "bad_request":
      return "Request rejected"
    case "invalid_response":
      return "Unexpected response"
    case "server":
      return "Query failed"
  }
}

/** The action that would clear the condition, when there is one. */
export function errorHint(error: ApiError): string | null {
  if (error.hint) return error.hint
  switch (error.kind) {
    case "network":
      return "Start the backend service, then retry."
    case "database_unavailable":
      return (
        "The database runs on the workstation at 100.69.116.8 and is reached over its IP. " +
        "Check that the workstation is up and the tunnel to it is active."
      )
    case "data_unavailable":
      return "Refresh the deployment's static export, then retry this application route."
    case "llm_not_configured":
      return "Add a model connection on the server, then refresh the connection status. Records can be viewed separately."
    case "model_unavailable":
      return "Check the configured model, API credentials and service availability, then retry."
    case "invalid_model_output":
      return "The model's answer failed its data or reference checks. Try a more specific question; no record text has been substituted."
    case "not_found":
      return "The identifier does not exist in the database."
    case "bad_request":
      return "The request carried a parameter the service does not accept."
    default:
      return null
  }
}
