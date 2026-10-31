import { useEffect, useState } from 'react'
import { ApiError } from '../services/api'

export const errorMessage = (e: unknown): string =>
  e instanceof ApiError ? e.message : 'Something went wrong while talking to the backend.'

interface AsyncState<T> { data: T | null; error: string | null; loading: boolean }

/** Runs `fn` whenever deps change, aborting the previous call and ignoring stale results. */
export function useAsync<T>(
  fn: ((signal: AbortSignal) => Promise<T>) | null,
  deps: unknown[],
): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: fn !== null })

  useEffect(() => {
    if (!fn) {
      setState({ data: null, error: null, loading: false })
      return
    }
    const ctl = new AbortController()
    setState({ data: null, error: null, loading: true })
    fn(ctl.signal)
      .then((data) => { if (!ctl.signal.aborted) setState({ data, error: null, loading: false }) })
      .catch((e) => { if (!ctl.signal.aborted) setState({ data: null, error: errorMessage(e), loading: false }) })
    return () => ctl.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}
