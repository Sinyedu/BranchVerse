import { Loader2 } from 'lucide-react'
import { useAsync } from '../../hooks/useAsync'
import { SERIES_A, SERIES_B } from '../../lib/colors'
import { formatDate } from '../../lib/formatters'
import { api } from '../../services/api'
import { BarChart } from './BarChart'

function Card({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-4 py-3">
      <p className="text-mute">{label}</p>
      <p className="mt-0.5 truncate text-xl font-semibold">{value}</p>
      {sub && <p className="truncate text-[12px] text-mute">{sub}</p>}
    </div>
  )
}

export function AnalyticsDashboard() {
  const { data, error, loading } = useAsync((s) => api.analytics(s), [])
  if (loading) return <p className="flex items-center gap-2 p-6 text-mute"><Loader2 size={14} className="animate-spin" /> Crunching history…</p>
  if (error) return <p role="alert" className="p-6 text-del">{error}</p>
  if (!data) return null
  if (data.total_commits === 0) return <p className="p-6 text-mute">No commits to analyse yet.</p>

  const top = data.contributors[0]?.commits ?? 1
  return (
    <div className="h-full overflow-y-auto p-5 fade-in">
      <h2 className="text-lg font-semibold">Analytics</h2>
      <p className="mb-4 mt-1 max-w-3xl text-mute">{data.scope_note}</p>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card label="Unique commits" value={data.total_commits.toLocaleString()} sub="reachable from any ref" />
        <Card label="Contributors" value={data.contributor_count.toLocaleString()} sub="distinct author emails" />
        <Card label="Branches" value={`${data.local_branches} local`} sub={`${data.remote_branches} remote-tracking`} />
        <Card label="Most commits" value={data.top_contributor?.name ?? '—'}
          sub={data.top_contributor ? `${data.top_contributor.commits.toLocaleString()} commits` : undefined} />
        <Card label="First commit" value={formatDate(data.first_commit)} />
        <Card label="Latest commit" value={formatDate(data.latest_commit)} />
      </div>

      <div className="mt-5 space-y-4">
        <BarChart title="Commits per week" data={data.weekly_commits}
          series={[{ key: 'commits', label: 'Commits', color: SERIES_A }]} emptyText="No commits in range." />
        {data.changes_available ? (
          <BarChart title={`Lines changed per week · ${data.changes_days} days before the newest commit`}
            data={data.weekly_changes}
            series={[{ key: 'additions', label: 'Additions', color: SERIES_A }, { key: 'deletions', label: 'Deletions', color: SERIES_B }]}
            emptyText="No line changes in this period." />
        ) : (
          <p className="rounded-lg border border-line bg-panel p-4 text-mute">
            Line-change statistics need file contents, which are not downloaded for repositories opened from GitHub.
            Commit, contributor and branch analytics above are complete.
          </p>
        )}

        <section className="rounded-lg border border-line bg-panel p-4">
          <h3 className="font-semibold">Contributors by commit count</h3>
          <p className="mb-3 text-[12px] text-mute">
            Commit count is not a measure of productivity or impact — commit sizes and styles vary widely.
            {data.scan_truncated && ` Based on the newest ${data.scan_limit.toLocaleString()} commits.`}
          </p>
          <ul className="space-y-1.5">
            {data.contributors.map((c) => (
              <li key={c.email} className="flex items-center gap-3">
                <span className="w-40 shrink-0 truncate" title={c.email}>{c.name}</span>
                <span className="h-2.5 flex-1 rounded-sm bg-raised">
                  <span className="block h-full rounded-sm" style={{ width: `${(c.commits / top) * 100}%`, background: SERIES_A }} />
                </span>
                <span className="w-12 text-right font-mono">{c.commits.toLocaleString()}</span>
              </li>
            ))}
          </ul>
          {data.contributor_count > data.contributors.length &&
            <p className="mt-2 text-mute">…and {data.contributor_count - data.contributors.length} more.</p>}
        </section>
      </div>
    </div>
  )
}
