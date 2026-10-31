import { Loader2 } from 'lucide-react'
import { useAsync } from '../../hooks/useAsync'
import { api } from '../../services/api'
import type { Strategy } from '../../types/git'

const STYLES: Record<Strategy['style'], { title: string; blurb: string }> = {
  'trunk-based': {
    title: 'Trunk-based',
    blurb: 'Everyone integrates small changes into one main line, often several times a day. Few or no long-lived branches; feature flags hide unfinished work.',
  },
  'feature-branch': {
    title: 'Feature-branch workflow',
    blurb: 'Each change lives on its own short-lived branch and is merged back (often via pull request) with a merge commit. Main stays releasable.',
  },
  'gitflow-like': {
    title: 'GitFlow-like',
    blurb: 'A long-lived develop branch collects features; release and hotfix branches stabilise and patch production. Powerful but heavy for continuously-deployed projects.',
  },
  unclear: {
    title: 'Not enough signal',
    blurb: 'There is not enough branch or merge history to describe a strategy.',
  },
}

export function StrategyView() {
  const { data, error, loading } = useAsync((s) => api.strategy(s), [])
  if (loading) return <p className="flex items-center gap-2 p-6 text-mute"><Loader2 size={14} className="animate-spin" /> Analysing branching strategy…</p>
  if (error) return <p role="alert" className="p-6 text-del">{error}</p>
  if (!data) return null
  const style = STYLES[data.style]

  return (
    <div className="h-full overflow-y-auto p-5 fade-in">
      <h2 className="text-lg font-semibold">Branching strategy</h2>
      <p className="mb-4 mt-1 max-w-2xl text-mute">
        What this repository's history <em>looks like</em>, inferred from measurable evidence.
        It is a heuristic description, not a judgement of quality.
      </p>

      <section className="max-w-3xl rounded-lg border border-line bg-panel p-4">
        <p className="text-[11px] uppercase tracking-wide text-mute">Looks like</p>
        <h3 className="text-xl font-semibold text-accent">{style.title}</h3>
        <p className="mt-1">{data.summary}</p>
        <p className="mt-2 text-mute">{style.blurb}</p>
      </section>

      <h3 className="mb-2 mt-6 font-semibold">Evidence</h3>
      <dl className="grid max-w-3xl gap-2">
        {data.evidence.map((e) => (
          <div key={e.label} className="rounded border border-line bg-panel px-3 py-2">
            <div className="flex justify-between gap-4"><dt className="text-mute">{e.label}</dt><dd className="font-mono">{e.value}</dd></div>
            <p className="mt-0.5 text-[12px] text-mute/80">{e.detail}</p>
          </div>
        ))}
      </dl>

      <div className="mt-6 grid max-w-3xl gap-4 md:grid-cols-2">
        <BranchList title="Merged branches" empty="None yet" names={data.merged_branches} tone="text-add" />
        <BranchList title="Not merged" empty="Everything is merged" names={data.unmerged_branches} tone="text-warn" />
      </div>
    </div>
  )
}

function BranchList({ title, names, empty, tone }: { title: string; names: string[]; empty: string; tone: string }) {
  return (
    <section>
      <h3 className="mb-1 font-semibold">{title} <span className="font-normal text-mute">({names.length})</span></h3>
      {names.length === 0 ? <p className="text-mute">{empty}</p> : (
        <ul className="space-y-0.5">{names.map((n) => <li key={n} className={`font-mono ${tone}`}>{n}</li>)}</ul>
      )}
    </section>
  )
}
