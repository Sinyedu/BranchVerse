import { Loader2, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Highlight } from '../../hooks/useRepository'
import { layoutGraph } from '../../lib/graphLayout'
import { scrollToRow, visibleRange, type Range } from '../../lib/virtual'
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

const sameRange = (a: Range, b: Range) => a.start === b.start && a.end === b.end

export function CommitGraph(p: Props) {
  const [hovered, setHovered] = useState<string | null>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const [range, setRange] = useState<Range>({ start: 0, end: 40 })
  // Layout is the expensive part: recompute only when the loaded commits change.
  const layout = useMemo(() => layoutGraph(p.commits), [p.commits])
  const index = useMemo(() => new Map(p.commits.map((c, i) => [c.sha, i])), [p.commits])
  const width = PAD * 2 + layout.laneCount * LANE_W
  const total = p.commits.length
  const hl = p.highlight
  const dim = useCallback((sha: string) => (hl ? !hl.shas.has(sha) : false), [hl])

  // Windowing: only rows near the viewport are in the DOM, however long the history is.
  const measure = useCallback(() => {
    const el = scroller.current
    if (!el) return
    const next = visibleRange(el.scrollTop, el.clientHeight || 800, ROW_H, total)
    setRange((r) => (sameRange(r, next) ? r : next))
  }, [total])
  useEffect(() => {
    measure()
    const el = scroller.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [measure])

  useEffect(() => {
    const el = scroller.current
    const i = p.selected ? index.get(p.selected) : undefined
    if (!el || i === undefined) return
    const top = scrollToRow(i, ROW_H, el.scrollTop, el.clientHeight || 800)
    if (top !== null) el.scrollTop = top
  }, [p.selected, index])

  if (total === 0) return <div className="p-8 text-center text-mute">This repository has no commits yet.</div>

  return (
    <div className="flex h-full flex-col">
      {hl && (
        <div className="flex items-center gap-2 border-b border-line bg-accent/10 px-3 py-1.5 text-accent">
          <span>Highlighting commits reachable from <b>{hl.name}</b>{hl.truncated && ' (first 20,000 only)'}</span>
          <button onClick={p.onClearHighlight} className="ml-auto flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-accent/20">
            <X size={12} /> Clear
          </button>
        </div>
      )}
      <div ref={scroller} onScroll={measure} className="min-h-0 flex-1 overflow-y-auto">
        <div className="relative" style={{ height: total * ROW_H + (p.hasMore ? ROW_H : 0) }}>
          <GraphEdges layout={layout} commits={p.commits} range={range} selected={p.selected} dim={dim}
            hovered={hovered} hasMore={p.hasMore} />
          {p.commits.slice(range.start, range.end).map((c, k) => (
            <CommitNode key={c.sha} commit={c} row={range.start + k} paddingLeft={width} selected={c.sha === p.selected}
              dimmed={dim(c.sha)} onSelect={p.onSelect} onHover={setHovered} />
          ))}
          {p.hasMore && (
            <div style={{ position: 'absolute', top: total * ROW_H, height: ROW_H, paddingLeft: width }}
              className="flex items-center text-mute">Older history continues…</div>
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
            <p className="text-mute">Reached the first commit · {total.toLocaleString()} loaded</p>
          )}
        </div>
      </div>
    </div>
  )
}
