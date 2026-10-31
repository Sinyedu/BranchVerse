import { ExternalLink, GitPullRequest, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useAsync } from '../../hooks/useAsync'
import { parsePullNumber } from '../../lib/pull'
import { api } from '../../services/api'
import type { PullMeta } from '../../types/git'
import { ComparisonResult } from './ComparisonResult'

const stateStyle: Record<PullMeta['state'], string> = {
  open: 'bg-add/15 text-add', merged: 'bg-[#9085e9]/20 text-[#9085e9]',
  closed: 'bg-del/15 text-del', unknown: 'bg-raised text-mute',
}

/** Look up a GitHub pull request by number (repositories opened from GitHub only). */
export function PullViewer() {
  const [input, setInput] = useState('')
  const [number, setNumber] = useState<number | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const pr = useAsync(number ? (s) => api.pull(number, s) : null, [number])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const n = parsePullNumber(input)
    setFormError(n === null ? 'Enter a pull request number such as 1234, #1234, or a GitHub pull request link.' : null)
    if (n !== null) setNumber(n)
  }
  const m = pr.data?.meta

  return (
    <div>
      <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
        <label htmlFor="pr-number" className="text-mute">Pull request</label>
        <input id="pr-number" value={input} onChange={(e) => setInput(e.target.value)} placeholder="#123 or PR link"
          className="w-56 rounded border border-line bg-panel px-2 py-1 font-mono" aria-invalid={formError ? true : undefined} />
        <button type="submit" disabled={pr.loading}
          className="flex items-center gap-1.5 rounded border border-accent bg-accent/10 px-3 py-1 text-accent hover:bg-accent/20 disabled:opacity-50">
          {pr.loading ? <Loader2 size={13} className="animate-spin" /> : <GitPullRequest size={13} />} Load
        </button>
      </form>
      {formError && <p role="alert" className="mt-2 text-del">{formError}</p>}
      {pr.loading && <p className="mt-4 text-mute">Fetching pull request from GitHub…</p>}
      {pr.error && <p role="alert" className="mt-4 text-del">{pr.error}</p>}

      {pr.data && m && (
        <ComparisonResult c={pr.data.compare} loadDiff={(path, s) => api.pullDiff(m.number, path, s)}
          summary={(
            <div>
              <p className="flex flex-wrap items-center gap-2 text-[15px]">
                <b>{m.title}</b> <span className="text-mute">#{m.number}</span>
                <span className={`rounded px-1.5 py-px text-[11px] ${stateStyle[m.state]}`}>{m.draft ? 'draft' : m.state}</span>
                <a href={m.url} target="_blank" rel="noopener noreferrer" className="ml-auto flex items-center gap-1 text-accent hover:underline">
                  View on GitHub <ExternalLink size={12} aria-hidden />
                </a>
              </p>
              <p className="mt-1 text-mute">
                {m.author ? <>by <b className="text-ink">{m.author}</b> · </> : null}
                {m.head_label ? <span className="font-mono">{m.head_label}</span> : 'head'} → <span className="font-mono">{m.base_ref ?? 'base'}</span>
              </p>
              {m.note && <p className="mt-1 text-[12px] text-warn">{m.note}</p>}
              {m.body && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-mute">Description</summary>
                  <pre className="mt-1 max-h-60 overflow-auto whitespace-pre-wrap break-words font-sans">{m.body}</pre>
                </details>
              )}
            </div>
          )} />
      )}
    </div>
  )
}
