/**
 * Data-fetching hooks for the pages.
 *
 * The pages were synchronous before this rewrite: each one imported a static module and read
 * from it. Real data arrives asynchronously, so every page needs the same three states and
 * the same retry affordance. Two hooks cover all of it — `useAsync` for something a page
 * needs on mount, `useAsyncAction` for something a click triggers.
 *
 * Staleness is handled explicitly in both. A page whose filter changes twice in quick
 * succession would otherwise be able to render the response to the first request after the
 * second one lands, which is the kind of bug that looks like wrong data rather than like a
 * race.
 */
import { useCallback, useEffect, useRef, useState } from "react"

import { ApiError } from "@/api/client"

function toApiError(cause: unknown): ApiError {
  if (cause instanceof ApiError) return cause
  return new ApiError("invalid_response", "The request failed before it produced a result.", {
    detail: cause instanceof Error ? cause.message : String(cause),
  })
}

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: ApiError | null
  /** True while a reload is in flight and previous data is still on screen. */
  refreshing: boolean
  reload: () => void
}

/**
 * Runs `run` on mount and again whenever `deps` change, keeping the latest result.
 *
 * `run` is read from a ref, so an inline arrow function does not retrigger the effect.
 */
export function useAsync<T>(run: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)

  const runRef = useRef(run)
  runRef.current = run

  // Identifies the newest request so an older one cannot overwrite its result.
  const sequence = useRef(0)
  const hasData = useRef(false)

  useEffect(() => {
    const ticket = ++sequence.current
    if (hasData.current) setRefreshing(true)
    else setLoading(true)
    setError(null)

    runRef
      .current()
      .then((result) => {
        if (ticket !== sequence.current) return
        hasData.current = true
        setData(result)
      })
      .catch((cause: unknown) => {
        if (ticket !== sequence.current) return
        setError(toApiError(cause))
      })
      .finally(() => {
        if (ticket !== sequence.current) return
        setLoading(false)
        setRefreshing(false)
      })

    return () => {
      // Bumping the sequence invalidates the in-flight request: its callbacks see a stale
      // ticket and return without touching state.
      if (ticket === sequence.current) sequence.current += 1
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  return { data, loading, error, refreshing, reload }
}

export interface AsyncAction<TArgs extends unknown[], TResult> {
  run: (...args: TArgs) => Promise<TResult | null>
  pending: boolean
  error: ApiError | null
  /** The most recent successful result, kept so a caller can render what it produced. */
  data: TResult | null
  reset: () => void
}

/**
 * Wraps a call the user triggers, exposing a pending flag and the failure.
 *
 * Returns `null` instead of throwing when the call fails, so a click handler does not need a
 * try/catch around every invocation; the error is available on the returned object.
 */
export function useAsyncAction<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
): AsyncAction<TArgs, TResult> {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [data, setData] = useState<TResult | null>(null)
  const actionRef = useRef(action)
  actionRef.current = action
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const run = useCallback(async (...args: TArgs) => {
    setPending(true)
    setError(null)
    try {
      const result = await actionRef.current(...args)
      if (mounted.current) setData(result)
      return result
    } catch (cause) {
      if (mounted.current) setError(toApiError(cause))
      return null
    } finally {
      if (mounted.current) setPending(false)
    }
  }, [])

  const reset = useCallback(() => {
    setError(null)
    setData(null)
  }, [])

  return { run, pending, error, data, reset }
}
