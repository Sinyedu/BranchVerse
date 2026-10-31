import { Suspense, lazy, useEffect, useState } from 'react'
import { CommitInspector } from './components/commits/CommitInspector'
import { CommitGraph } from './components/graph/CommitGraph'
import { AppLayout } from './components/layout/AppLayout'
import type { View } from './components/layout/Sidebar'
import { Welcome, rememberRepo } from './components/layout/Welcome'
import { useRepository } from './hooks/useRepository'

// Secondary views load on first use, keeping the initial bundle small.
const AnalyticsDashboard = lazy(() => import('./components/analytics/AnalyticsDashboard').then((m) => ({ default: m.AnalyticsDashboard })))
const BranchExplorer = lazy(() => import('./components/branches/BranchExplorer').then((m) => ({ default: m.BranchExplorer })))
const LearnView = lazy(() => import('./components/learn/LearnView').then((m) => ({ default: m.LearnView })))
const CompareView = lazy(() => import('./components/compare/CompareView').then((m) => ({ default: m.CompareView })))
const StrategyView = lazy(() => import('./components/strategy/StrategyView').then((m) => ({ default: m.StrategyView })))
const GitTimeMachine = lazy(() => import('./components/timeline/GitTimeMachine').then((m) => ({ default: m.GitTimeMachine })))

export default function App() {
  const r = useRepository()
  const [view, setView] = useState<View>('graph')
  const [picking, setPicking] = useState(true)
  const hasRepo = r.repo !== null && r.status !== 'error'

  // A successful open leaves the picker and lands on the commit graph.
  useEffect(() => {
    if (r.status === 'ready' && r.repo) { setPicking(false); rememberRepo(r.repo.path) }
  }, [r.status, r.repo])

  const open = (path: string) => { setView('graph'); r.open(path) }
  const showWelcome = view !== 'learn' && (picking || !hasRepo)

  let content
  if (view === 'learn') content = <LearnView hasRepo={hasRepo} onOpenStrategy={() => setView('strategy')} />
  else if (showWelcome) {
    content = (
      <Welcome loading={r.status === 'loading'} error={r.error} onOpen={open} onLearn={() => setView('learn')}
        onCancel={hasRepo ? () => setPicking(false) : undefined} />
    )
  } else if (view === 'graph') {
    content = r.repo?.is_empty ? <p className="p-8 text-center text-mute">This repository is empty — make a first commit and reopen it.</p> : (
      <CommitGraph commits={r.commits} selected={r.selected} highlight={r.highlight} hasMore={r.hasMore}
        loadingMore={r.loadingMore} moreError={r.moreError} onSelect={r.select} onLoadMore={r.loadMore}
        onClearHighlight={() => r.highlightBranch(null)} />
    )
  } else if (view === 'branches') {
    content = <BranchExplorer highlight={r.highlight} onHighlight={r.highlightBranch} onShowGraph={() => setView('graph')} />
  } else if (view === 'compare') content = <CompareView isGitHub={!!r.repo?.remote_url} />
  else if (view === 'strategy') content = <StrategyView />
  else if (view === 'analytics') content = <AnalyticsDashboard />
  else content = <GitTimeMachine />

  const inspector = view === 'graph' && !showWelcome && !r.repo?.is_empty
    ? <CommitInspector sha={r.selected} onSelect={r.select} /> : null

  return (
    <AppLayout repo={hasRepo ? r.repo : null} commitCount={r.commits.length} hasMore={r.hasMore} view={view}
      onView={(v) => { setView(v); if (v !== 'learn') setPicking(!hasRepo) }}
      onSwitchRepo={() => { setView('graph'); setPicking(true) }} inspector={inspector}>
      <Suspense fallback={<p className="p-6 text-mute">Loading…</p>}>{content}</Suspense>
    </AppLayout>
  )
}
