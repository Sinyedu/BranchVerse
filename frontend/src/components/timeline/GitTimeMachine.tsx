import { ChevronLeft, ChevronRight, Loader2, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime } from '../../lib/formatters'
import { clampIndex, isPresent, presentIndex, stepIndex } from '../../lib/timeline'
import { api } from '../../services/api'
import type { PathChange, Timeline } from '../../types/git'

function FileCountChart({ tl, index }: { tl: Timeline; index: number }) {
  const counts = tl.commits.map((c) => c.file_count)
  if (counts.some((c) => c === null) || counts.length < 2) return null
  const values = counts as number[]
  const max = Math.max(...values, 1)
  const W = 600, H = 60
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * W},${H - (v / max) * (H - 6) - 3}`).join(' ')
  const x = (index / (values.length - 1)) * W
  return (
    <figure className="mt-4">
      <figcaption className="mb-1 text-mute">Tracked files over time (peak {max})</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-16 w-full" preserveAspectRatio="none" role="img" aria-label="Tracked file count over time">
        <polyline points={pts} fill="none" stroke="#3987e5" strokeWidth={2} vectorEffect="non-scaling-stroke" />
        <line x1={x} x2={x} y1={0} y2={H} stroke="#e6e8eb" strokeWidth={1} vectorEffect="non-scaling-stroke" />
      </svg>
    </figure>
  )
}

function ChangeList({ title, items, tone }: { title: string; items: PathChange[]; tone: string }) {
  if (items.length === 0) return null
  return (
    <div className="min-w-0">
      <h4 className={`font-semibold ${tone}`}>{title} ({items.length})</h4>
      <ul className="max-h-40 overflow-y-auto font-mono text-[12px]">
        {items.map((p) => <li key={p.path} className="truncate" title={p.path}>{p.old_path ? `${p.old_path} → ` : ''}{p.path}</li>)}
      </ul>
    </div>
  )
}

export function GitTimeMachine() {
  const timeline = useAsync((s) => api.timeline(s), [])
  const commits = timeline.data?.commits ?? []
  const [index, setIndex] = useState<number | null>(null)
  const length = commits.length
  const current = clampIndex(index ?? presentIndex(length), length)
  const sha = commits[current]?.sha ?? null
  const snap = useAsync(sha ? (s) => api.snapshot(sha, s) : null, [sha])

  useEffect(() => setIndex(null), [timeline.data])

  if (timeline.loading) return <p className="flex items-center gap-2 p-6 text-mute"><Loader2 size={14} className="animate-spin" /> Loading timeline…</p>
  if (timeline.error) return <p role="alert" className="p-6 text-del">{timeline.error}</p>
  if (length === 0) return <p className="p-6 text-mute">{timeline.data?.note ?? 'No history to explore.'}</p>

  const commit = commits[current]
  const s = snap.data
  const present = isPresent(current, length)

  return (
    <div className="h-full overflow-y-auto p-5 fade-in">
      <h2 className="text-lg font-semibold">Git Time Machine</h2>
      <p className="mt-1 max-w-3xl text-mute">
        Explore historical snapshots along the current branch's first-parent history. Nothing is checked out —
        every file list is read straight from Git's object store.
      </p>

      <section className="mt-4 max-w-3xl rounded-lg border border-line bg-panel p-4">
        <div className="flex items-center gap-2">
          <button aria-label="Previous snapshot" disabled={current === 0} onClick={() => setIndex(stepIndex(current, -1, length))}
            className="rounded border border-line p-1 hover:border-accent disabled:opacity-40"><ChevronLeft size={16} /></button>
          <input type="range" min={0} max={length - 1} value={current} aria-label="Timeline position"
            onChange={(e) => setIndex(Number(e.target.value))} className="flex-1 accent-accent" />
          <button aria-label="Next snapshot" disabled={present} onClick={() => setIndex(stepIndex(current, 1, length))}
            className="rounded border border-line p-1 hover:border-accent disabled:opacity-40"><ChevronRight size={16} /></button>
          <button onClick={() => setIndex(null)} disabled={present}
            className="flex items-center gap-1 rounded border border-line px-2 py-1 hover:border-accent disabled:opacity-40">
            <RotateCcw size={13} /> Return to present
          </button>
        </div>
        <div className="mt-1 flex justify-between text-[11px] text-mute">
          <span>oldest</span><span>snapshot {current + 1} of {length.toLocaleString()}{present && ' · present (HEAD)'}</span><span>newest</span>
        </div>

        <div key={commit.sha} className="mt-3 fade-in">
          <p className="text-base font-semibold">{commit.subject}</p>
          <p className="text-mute">
            {formatDateTime(commit.timestamp)} · {commit.author} · <span className="font-mono">{commit.short_sha}</span>
          </p>
        </div>
        <FileCountChart tl={timeline.data!} index={current} />
        {timeline.data?.truncated && <p className="mt-2 text-warn">{timeline.data.note}</p>}
      </section>

      <section className="mt-4 max-w-3xl">
        {snap.loading && <p className="flex items-center gap-2 text-mute"><Loader2 size={14} className="animate-spin" /> Reading snapshot…</p>}
        {snap.error && <p role="alert" className="text-del">{snap.error}</p>}
        {s && (
          <div className="fade-in">
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
              <p><span className="text-2xl font-semibold">{s.file_count.toLocaleString()}</span> <span className="text-mute">tracked files</span></p>
              <p className="text-mute">
                {s.previous_sha ? 'Since previous snapshot: ' : 'First snapshot: '}
                <span className="text-add">+{s.additions}</span> <span className="text-del">−{s.deletions}</span> lines
              </p>
            </div>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              <ChangeList title="Added" items={s.added} tone="text-add" />
              <ChangeList title="Deleted" items={s.deleted} tone="text-del" />
              <ChangeList title="Modified" items={s.modified} tone="text-warn" />
              <ChangeList title="Renamed" items={s.renamed} tone="text-accent" />
            </div>
            {s.changes_truncated && <p className="mt-2 text-warn">Change lists are limited to 200 entries each.</p>}
            <details className="mt-4 rounded-lg border border-line bg-panel p-3" open>
              <summary className="cursor-pointer font-semibold">Files at this snapshot</summary>
              <ul className="mt-2 max-h-72 overflow-y-auto font-mono text-[12px]">
                {s.files.map((f) => <li key={f} className="truncate" title={f}>{f}</li>)}
              </ul>
              {s.files_truncated && <p className="mt-1 text-warn">Showing the first 3,000 files.</p>}
            </details>
          </div>
        )}
      </section>
    </div>
  )
}
