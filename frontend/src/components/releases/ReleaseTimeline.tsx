import { Loader2, Tag } from 'lucide-react'
import { useAsync } from '../../hooks/useAsync'
import { formatDate, plural } from '../../lib/formatters'
import { barPercent, formatInterval, medianInterval } from '../../lib/releases'
import { api } from '../../services/api'

export function ReleaseTimeline() {
  const { data, error, loading } = useAsync((s) => api.releases(s), [])
  if (loading) return <p className="flex items-center gap-2 p-6 text-mute"><Loader2 size={14} className="animate-spin" /> Reading tags…</p>
  if (error) return <p role="alert" className="p-6 text-del">{error}</p>
  if (!data) return null
  const newest = [...data.releases].reverse()
  const median = medianInterval(data.releases)

  return (
    <div className="h-full overflow-y-auto p-5 fade-in">
      <h2 className="text-lg font-semibold">Releases</h2>
      <p className="mb-4 mt-1 max-w-2xl text-mute">{data.note}</p>
      {newest.length === 0 ? (
        <p className="text-mute">Tag a commit (for example <code className="font-mono">git tag v1.0.0</code>) and reopen the repository to see it here.</p>
      ) : (
        <>
          <dl className="mb-5 grid max-w-3xl grid-cols-3 gap-2">
            <Tile label="Releases" value={data.total_tags.toLocaleString()} />
            <Tile label="Median gap" value={formatInterval(median)} />
            <Tile label="Latest" value={newest[0].name} mono />
          </dl>
          <ol className="max-w-3xl space-y-2">
            {newest.map((r) => (
              <li key={r.name} className="rounded-lg border border-line bg-panel p-3">
                <div className="flex flex-wrap items-baseline gap-x-3">
                  <Tag size={14} aria-hidden className="self-center text-accent" />
                  <span className="font-mono font-semibold">{r.name}</span>
                  <span className="text-mute">{formatDate(r.timestamp)}</span>
                  <span className="font-mono text-[12px] text-mute">{r.short_sha}</span>
                  {r.annotated && <span className="rounded bg-raised px-1.5 text-[11px] text-mute">annotated</span>}
                </div>
                {r.message && <p className="mt-1">{r.message}</p>}
                <div className="mt-2 flex flex-wrap items-center gap-3 text-[12px] text-mute">
                  <div className="h-2 w-40 rounded bg-raised" role="img"
                    aria-label={r.commits === null ? 'Commit count unavailable' : plural(r.commits, 'commit')}>
                    <div className="h-2 rounded bg-accent" style={{ width: `${barPercent(r.commits, data.releases)}%` }} />
                  </div>
                  <span>{r.commits === null ? 'commits unavailable' : plural(r.commits, 'commit')}</span>
                  {r.contributors !== null && <span>{plural(r.contributors, 'contributor')}</span>}
                  <span>{r.previous ? `${formatInterval(r.days_since_previous)} after ${r.previous}` : 'first release'}</span>
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  )
}

function Tile({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded border border-line bg-panel px-3 py-2">
      <dt className="text-[11px] uppercase tracking-wide text-mute">{label}</dt>
      <dd className={`truncate text-lg ${mono ? 'font-mono' : ''}`}>{value}</dd>
    </div>
  )
}
