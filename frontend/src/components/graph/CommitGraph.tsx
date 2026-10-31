import { Loader2, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { Highlight } from '../../hooks/useRepository'
import { layoutGraph } from '../../lib/graphLayout'
import type { Commit } from '../../types/git'
import { CommitNode } from './CommitNode'
import { GraphEdges, LANE_W, PAD, ROW_H } from './GraphEdges'

interface Props {
  commits: Commit[]
  selected: string | null
  highlight: Highlight | null
  hasMore: boolean
  loadingMore: boolean
  moreError: string | null
  onSelect: (sha: string) => void
  onLoadMore: () => void
  onClearHighlight: () => void
}

export function CommitGraph(p: Props) {
  const [hovered, setHovered] = useState<string | null>(null)
  // Layout is the expensive part: recompute only when the loaded commits change.
  const layout = useMemo(() => layoutGraph(p.commits), [p.commits])
  const width = PAD * 2 + layout.laneCount * LANE_W
  const dim = (sha: string) => (p.highlight ? !p.highlight.shas.has(sha) : false)

  useEffect(() => {
    if (p.selected) document.getElementById(`row-${p.selected}`)?.scrollIntoView({ block: 'nearest' })
  }, [p.selected])

  if (p.commits.length === 0) {
    return <div className="p-8 text-center text-mute">This repository has no commits yet.</div>
  }

  return (
    <div className="flex h-full flex-col">
      {p.highlight && (
        <div className="flex items-center gap-2 border-b border-line bg-accent/10 px-3 py-1.5 text-accent">
          <span>
            Highlighting commits reachable from <b>{p.highlight.name}</b>
            {p.highlight.truncated && ' (first 20,000 only)'}
          </span>
          <button onClick={p.onClearHighlight} className="ml-auto flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-accent/20">
            <X size={12} /> Clear
          </button>
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="relative">
          <GraphEdges layout={layout} commits={p.commits} selected={p.selected} dim={dim}
            hovered={hovered} hasMore={p.hasMore} />
          {p.commits.map((c) => (
            <CommitNode key={c.sha} commit={c} paddingLeft={width} selected={c.sha === p.selected}
              dimmed={dim(c.sha)} onSelect={() => p.onSelect(c.sha)} onHover={setHovered} />
          ))}
          {p.hasMore && (
            <div style={{ height: ROW_H, paddingLeft: width }} className="flex items-center text-mute">
              Older history continues…
            </div>
          )}
        </div>
        <div className="flex flex-col items-center gap-2 p-4">
          {p.moreError && <p role="alert" className="text-del">{p.moreError}</p>}
          {p.hasMore ? (
            <button onClick={p.onLoadMore} disabled={p.loadingMore}
              className="flex items-center gap-2 rounded border border-line bg-raised px-3 py-1.5 hover:border-accent disabled:opacity-60">
              {p.loadingMore && <Loader2 size={14} className="animate-spin" />}
              {p.loadingMore ? 'Loading…' : 'Load more commits'}
            </button>
          ) : (
            <p className="text-mute">Reached the first commit · {p.commits.length.toLocaleString()} loaded</p>
          )}
        </div>
      </div>
    </div>
  )
}
