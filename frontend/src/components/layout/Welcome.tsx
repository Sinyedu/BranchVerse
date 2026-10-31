import { BookOpen, FolderGit2, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { APP_NAME } from '../../lib/formatters'

const RECENT_KEY = 'branchverse.recent'

function loadRecent(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]')
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string').slice(0, 5) : []
  } catch { return [] }
}

export function rememberRepo(path: string) {
  try {
    const next = [path, ...loadRecent().filter((p) => p !== path)].slice(0, 5)
    localStorage.setItem(RECENT_KEY, JSON.stringify(next))
  } catch { /* storage unavailable: recents are only a convenience */ }
}

interface Props {
  loading: boolean
  error: string | null
  onOpen: (path: string) => void
  onLearn: () => void
  onCancel?: () => void
}

export function Welcome({ loading, error, onOpen, onLearn, onCancel }: Props) {
  const [path, setPath] = useState('')
  const recent = loadRecent()
  const submit = (p: string) => { if (p.trim() && !loading) onOpen(p.trim()) }

  return (
    <div className="flex h-full items-center justify-center overflow-y-auto p-6">
      <div className="w-full max-w-xl fade-in">
        <h1 className="text-4xl font-bold tracking-tight">{APP_NAME}</h1>
        <p className="mt-2 text-[15px] text-mute">Understand your repository. Explore its history.</p>

        <form className="mt-8" onSubmit={(e) => { e.preventDefault(); submit(path) }}>
          <label htmlFor="repo-path" className="mb-1 block text-mute">Path to a local Git repository</label>
          <div className="flex gap-2">
            <input id="repo-path" value={path} onChange={(e) => setPath(e.target.value)} autoFocus spellCheck={false}
              placeholder="C:\Users\you\projects\my-repo" aria-invalid={error ? true : undefined}
              className="min-w-0 flex-1 rounded border border-line bg-panel px-3 py-2 font-mono" />
            <button type="submit" disabled={loading || !path.trim()}
              className="flex items-center gap-2 rounded bg-accent px-4 py-2 font-medium text-bg hover:brightness-110 disabled:opacity-50">
              {loading ? <Loader2 size={15} className="animate-spin" /> : <FolderGit2 size={15} />}
              {loading ? 'Opening…' : 'Open Repository'}
            </button>
          </div>
          {error && <p role="alert" className="mt-2 text-del">{error}</p>}
          <p className="mt-2 text-[12px] text-mute">
            Read-only and local: {APP_NAME} never changes your repository or contacts the network.
          </p>
        </form>

        {recent.length > 0 && (
          <div className="mt-6">
            <h2 className="mb-1 text-[11px] uppercase tracking-wide text-mute">Recent</h2>
            <ul>
              {recent.map((r) => (
                <li key={r}><button onClick={() => submit(r)} className="w-full truncate rounded px-2 py-1 text-left font-mono text-[12px] text-accent hover:bg-raised">{r}</button></li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-8 flex items-center gap-3 border-t border-line pt-5">
          <button onClick={onLearn} className="flex items-center gap-2 rounded border border-line px-3 py-2 hover:border-accent">
            <BookOpen size={15} /> New to branching? Start learning
          </button>
          {onCancel && <button onClick={onCancel} className="ml-auto text-mute hover:text-ink">Cancel</button>}
        </div>
      </div>
    </div>
  )
}
