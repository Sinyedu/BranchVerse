import { ArrowDown, ArrowUp, GitBranch, Globe, Loader2 } from 'lucide-react'
import { useAsync } from '../../hooks/useAsync'
import type { Highlight } from '../../hooks/useRepository'
import { formatDate } from '../../lib/formatters'
import { api } from '../../services/api'
import type { Branch } from '../../types/git'

function Comparison({ b }: { b: Branch }) {
  const c = b.comparison
  if (c.kind === 'none' || c.ahead === null || c.behind === null) {
    return <span className="text-mute">{c.note ?? 'No comparison available'}</span>
  }
  const label = c.kind === 'upstream' ? 'upstream' : 'default branch'
  return (
    <span className="flex items-center gap-2">
      <span className="flex items-center text-add"><ArrowUp size={12} />{c.ahead}</span>
      <span className="flex items-center text-warn"><ArrowDown size={12} />{c.behind}</span>
      <span className="text-mute">vs <span className="font-mono">{c.base}</span> ({label})</span>
    </span>
  )
}

interface Props {
  highlight: Highlight | null
  onHighlight: (b: Branch | null) => void
  onShowGraph: () => void
}

export function BranchExplorer({ highlight, onHighlight, onShowGraph }: Props) {
  const branches = useAsync((s) => api.branches(s), [])
  const strategy = useAsync((s) => api.strategy(s), [])

  if (branches.loading) return <p className="flex items-center gap-2 p-6 text-mute"><Loader2 size={14} className="animate-spin" /> Loading branches…</p>
  if (branches.error) return <p role="alert" className="p-6 text-del">{branches.error}</p>
  const list = branches.data?.branches ?? []
  if (list.length === 0) return <p className="p-6 text-mute">This repository has no branches yet.</p>

  const merged = new Set(strategy.data?.merged_branches ?? [])
  const def = branches.data?.default_branch

  return (
    <div className="h-full overflow-y-auto p-5 fade-in">
      <h2 className="text-lg font-semibold">Branches</h2>
      <p className="mb-4 mt-1 max-w-2xl text-mute">
        Select a branch to highlight every commit reachable from it in the graph.
        {def ? <> Comparisons without an upstream use <b className="text-ink">{def}</b> as the default branch.</>
          : ' No default branch could be identified, so branches without an upstream are not compared.'}
      </p>
      <ul className="divide-y divide-line rounded-lg border border-line bg-panel">
        {list.map((b) => {
          const active = highlight?.fullRef === b.full_ref
          return (
            <li key={b.full_ref}>
              <button onClick={() => (active ? onHighlight(null) : onHighlight(b))} aria-pressed={active}
                className={`flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-left hover:bg-raised ${active ? 'bg-accent/10' : ''}`}>
                {b.is_remote ? <Globe size={14} className="text-mute" aria-label="remote-tracking" /> : <GitBranch size={14} className="text-add" aria-label="local" />}
                <span className="min-w-40 font-mono font-medium">{b.name}</span>
                {b.is_current && <span className="rounded bg-accent/20 px-1.5 text-[11px] text-accent">current</span>}
                {b.name === def && <span className="rounded bg-raised px-1.5 text-[11px] text-mute">default</span>}
                {!b.is_remote && b.name !== def && strategy.data && (
                  merged.has(b.name)
                    ? <span className="rounded bg-add/10 px-1.5 text-[11px] text-add">merged into {def}</span>
                    : <span className="rounded bg-warn/10 px-1.5 text-[11px] text-warn">not merged into {def}</span>)}
                <span className="font-mono text-[11px] text-mute">{b.sha.slice(0, 7)}</span>
                <span className="text-mute">{formatDate(b.last_commit_date)}</span>
                <span className="ml-auto"><Comparison b={b} /></span>
              </button>
            </li>
          )
        })}
      </ul>
      {highlight && (
        <button onClick={onShowGraph} className="mt-4 rounded border border-accent bg-accent/10 px-3 py-1.5 text-accent hover:bg-accent/20">
          Show {highlight.name} in the graph
        </button>
      )}
    </div>
  )
}
