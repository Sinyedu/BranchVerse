import { useCallback, useRef, useState } from 'react'
import { api } from '../services/api'
import type { Branch, Commit, RepositoryInfo } from '../types/git'
import { looksLikeUrl } from '../lib/source'
import { errorMessage } from './useAsync'

export const PAGE_SIZE = 100

export interface Highlight { fullRef: string; name: string; shas: Set<string>; truncated: boolean }

interface State {
  status: 'idle' | 'loading' | 'ready' | 'error'
  repo: RepositoryInfo | null
  error: string | null
  commits: Commit[]
  hasMore: boolean
  loadingMore: boolean
  moreError: string | null
  selected: string | null
  highlight: Highlight | null
}

const initial: State = {
  status: 'idle', repo: null, error: null, commits: [], hasMore: false,
  loadingMore: false, moreError: null, selected: null, highlight: null,
}

export function useRepository() {
  const [state, setState] = useState<State>(initial)
  const generation = useRef(0) // bumped on every open: lets us drop stale responses
  const controller = useRef<AbortController | null>(null)
  const loaded = useRef(0)

  const open = useCallback(async (path: string) => {
    controller.current?.abort()
    const ctl = new AbortController()
    controller.current = ctl
    const mine = ++generation.current
    setState((s) => ({ ...initial, status: 'loading', repo: s.repo }))
    try {
      const repo = looksLikeUrl(path) ? await api.openUrl(path, ctl.signal) : await api.open(path, ctl.signal)
      const page = await api.commits(PAGE_SIZE, 0, ctl.signal)
      if (mine !== generation.current) return
      loaded.current = page.commits.length
      setState({
        ...initial, status: 'ready', repo, commits: page.commits, hasMore: page.has_more,
        selected: page.commits[0]?.sha ?? null,
      })
    } catch (e) {
      if (mine !== generation.current || ctl.signal.aborted) return
      setState({ ...initial, status: 'error', error: errorMessage(e) })
    }
  }, [])

  const loadMore = useCallback(async () => {
    const mine = generation.current
    setState((s) => ({ ...s, loadingMore: true, moreError: null }))
    try {
      const page = await api.commits(PAGE_SIZE, loaded.current, controller.current?.signal)
      if (mine !== generation.current) return
      loaded.current += page.commits.length
      setState((s) => ({
        ...s, loadingMore: false, hasMore: page.has_more,
        commits: [...s.commits, ...page.commits.filter((c) => !s.commits.some((x) => x.sha === c.sha))],
      }))
    } catch (e) {
      if (mine !== generation.current) return
      setState((s) => ({ ...s, loadingMore: false, moreError: errorMessage(e) }))
    }
  }, [])

  const select = useCallback((sha: string | null) => setState((s) => ({ ...s, selected: sha })), [])

  const highlightBranch = useCallback(async (branch: Branch | null) => {
    if (!branch) { setState((s) => ({ ...s, highlight: null })); return }
    const mine = generation.current
    try {
      const r = await api.reachable(branch.full_ref)
      if (mine !== generation.current) return
      setState((s) => ({
        ...s, highlight: { fullRef: branch.full_ref, name: branch.name, shas: new Set(r.shas), truncated: r.truncated },
      }))
    } catch (e) {
      if (mine === generation.current) setState((s) => ({ ...s, moreError: errorMessage(e) }))
    }
  }, [])

  return { ...state, open, loadMore, select, highlightBranch }
}
