import type {
  Analytics, BranchList, CommitDetails, CommitPage, FileDiff, Reachable,
  RepositoryInfo, Snapshot, Strategy, Timeline,
} from '../types/git'

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

const TOKEN_HEADER = 'X-BranchVerse-Token'
let tokenPromise: Promise<string> | null = null

const unavailable = () =>
  new ApiError(0, 'backend_unavailable',
    'Cannot reach the BranchVerse backend on 127.0.0.1:8000. Is it running?')

function getToken(): Promise<string> {
  tokenPromise ??= fetch('/api/session')
    .then((r) => (r.ok ? r.json() : Promise.reject(unavailable())))
    .then((j: { token: string }) => j.token)
    .catch(() => { tokenPromise = null; throw unavailable() })
  return tokenPromise
}

interface Init { method?: string; body?: unknown; signal?: AbortSignal }

async function request<T>(path: string, init: Init = {}, retry = true): Promise<T> {
  const token = await getToken()
  let res: Response
  try {
    res = await fetch(path, {
      method: init.method ?? 'GET',
      signal: init.signal,
      headers: { [TOKEN_HEADER]: token, ...(init.body ? { 'Content-Type': 'application/json' } : {}) },
      body: init.body ? JSON.stringify(init.body) : undefined,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw unavailable()
  }
  if (res.status === 401 && retry) { // backend restarted: fetch a fresh token once
    tokenPromise = null
    return request<T>(path, init, false)
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(res.status, body?.error?.code ?? 'error', body?.error?.message ?? `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

const q = (params: Record<string, string | number>) =>
  '?' + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString()

export const api = {
  open: (path: string, signal?: AbortSignal) =>
    request<RepositoryInfo>('/api/repositories/open', { method: 'POST', body: { path }, signal }),
  commits: (limit: number, offset: number, signal?: AbortSignal) =>
    request<CommitPage>('/api/commits' + q({ limit, offset }), { signal }),
  commit: (sha: string, signal?: AbortSignal) => request<CommitDetails>(`/api/commits/${sha}`, { signal }),
  diff: (sha: string, path: string, signal?: AbortSignal) =>
    request<FileDiff>(`/api/commits/${sha}/diff` + q({ path }), { signal }),
  branches: (signal?: AbortSignal) => request<BranchList>('/api/branches', { signal }),
  reachable: (ref: string, signal?: AbortSignal) =>
    request<Reachable>('/api/branches/reachable' + q({ ref }), { signal }),
  analytics: (signal?: AbortSignal) => request<Analytics>('/api/analytics', { signal }),
  strategy: (signal?: AbortSignal) => request<Strategy>('/api/strategy', { signal }),
  timeline: (signal?: AbortSignal) => request<Timeline>('/api/timeline', { signal }),
  snapshot: (sha: string, signal?: AbortSignal) => request<Snapshot>(`/api/timeline/${sha}`, { signal }),
}
