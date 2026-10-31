import { ArrowRight, GitPullRequest, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAsync } from '../../hooks/useAsync'
import { api } from '../../services/api'
import { ComparisonResult } from './ComparisonResult'
import { PullViewer } from './PullViewer'

type Mode = 'branches' | 'pull'

export function CompareView({ isGitHub }: { isGitHub: boolean }) {
  const [mode, setMode] = useState<Mode>('branches')
  const branches = useAsync((s) => api.branches(s), [])
  const list = branches.data?.branches ?? []
  const [base, setBase] = useState<string | null>(null)
  const [head, setHead] = useState<string | null>(null)

  // Sensible defaults: base = default branch, compare = another local branch.
  useEffect(() => {
    if (!branches.data) return
    const bs = branches.data.branches
    const def = bs.find((b) => b.name === branches.data!.default_branch && !b.is_remote) ?? bs[0]
    const other = bs.find((b) => b.full_ref !== def?.full_ref && !b.is_remote) ?? bs.find((b) => b.full_ref !== def?.full_ref)
    setBase(def?.full_ref ?? null)
    setHead(other?.full_ref ?? null)
  }, [branches.data])

  const cmp = useAsync(mode === 'branches' && base && head ? (s) => api.compare(base, head, s) : null, [mode, base, head])

  const select = (value: string | null, set: (v: string) => void, label: string) => (
    <label className="flex items-center gap-2">
      <span className="text-mute">{label}</span>
      <select value={value ?? ''} onChange={(e) => set(e.target.value)}
        className="max-w-56 rounded border border-line bg-panel px-2 py-1 font-mono">
        {list.map((b) => <option key={b.full_ref} value={b.full_ref}>{b.name}{b.is_remote ? ' (remote)' : ''}</option>)}
      </select>
    </label>
  )

  return (
    <div className="h-full overflow-y-auto p-5 fade-in">
      <h2 className="flex items-center gap-2 text-lg font-semibold"><GitPullRequest size={18} /> Compare</h2>
      <p className="mb-4 mt-1 max-w-3xl text-mute">
        See changes the way a pull request shows them: the commits added and the files changed, measured from where the
        work split off. Nothing is merged — this is a read-only preview.
      </p>

      {isGitHub && (
        <div role="tablist" className="mb-4 flex gap-1">
          {(['branches', 'pull'] as const).map((m) => (
            <button key={m} role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
              className={`rounded px-3 py-1 ${mode === m ? 'bg-raised text-accent' : 'text-mute hover:bg-raised'}`}>
              {m === 'branches' ? 'Two branches' : 'GitHub pull request'}
            </button>
          ))}
        </div>
      )}

      {mode === 'pull' ? <PullViewer /> : branches.loading ? (
        <p className="flex items-center gap-2 text-mute"><Loader2 size={14} className="animate-spin" /> Loading branches…</p>
      ) : branches.error ? <p role="alert" className="text-del">{branches.error}</p>
        : list.length < 2 ? <p className="text-mute">Comparing branches needs at least two branches.</p> : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              {select(base, setBase, 'base')}
              <ArrowRight size={14} className="text-mute" aria-hidden />
              {select(head, setHead, 'compare')}
            </div>
            {cmp.loading && <p className="mt-6 flex items-center gap-2 text-mute"><Loader2 size={14} className="animate-spin" /> Comparing…</p>}
            {cmp.error && <p role="alert" className="mt-6 text-del">{cmp.error}</p>}
            {cmp.data && <ComparisonResult key={`${base}|${head}`} c={cmp.data} loadDiff={(path, s) => api.compareDiff(base!, head!, path, s)} />}
          </>
        )}
    </div>
  )
}
