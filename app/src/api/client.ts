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
 */

export type ApiErrorKind =
  | "network"
  | "database_unavailable"
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
  const raw = import.meta.env.VITE_API_BASE as string | undefined
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
  if (body.error === "database_unavailable") return "database_unavailable"
  if (status === 404) return "not_found"
  if (status === 400 || status === 422) return "bad_request"
  if (status === 503) return "database_unavailable"
  return "server"
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${apiBase()}${path}`
  let response: Response
  try {
    response = await fetch(url, {
      headers: { Accept: "application/json" },
      ...init,
    })
  } catch (cause) {
    throw new ApiError(
      "network",
      "The API could not be reached.",
      {
        detail: cause instanceof Error ? cause.message : String(cause),
        hint:
          "Start the service (uvicorn app.main:app) and confirm the Vite dev server is " +
          "proxying /api to it.",
      },
    )
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
    case "not_found":
      return "The identifier does not exist in the database."
    case "bad_request":
      return "The request carried a parameter the service does not accept."
    default:
      return null
  }
}
