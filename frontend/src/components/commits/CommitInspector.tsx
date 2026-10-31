import { Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime } from '../../lib/formatters'
import { api } from '../../services/api'
import type { FileChange } from '../../types/git'
import { FileDiff } from './FileDiff'

const statusStyle: Record<FileChange['status'], [string, string]> = {
  added: ['A', 'text-add'], modified: ['M', 'text-warn'], deleted: ['D', 'text-del'],
  renamed: ['R', 'text-accent'], copied: ['C', 'text-accent'], other: ['?', 'text-mute'],
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 py-0.5">
      <dt className="w-16 shrink-0 text-mute">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  )
}

export function CommitInspector({ sha, onSelect }: { sha: string | null; onSelect: (sha: string) => void }) {
  const { data, error, loading } = useAsync(sha ? (s) => api.commit(sha, s) : null, [sha])
  const [file, setFile] = useState<string | null>(null)
  useEffect(() => setFile(null), [sha])

  if (!sha) return <p className="p-4 text-mute">Select a commit to inspect it.</p>
  if (loading) return <p className="flex items-center gap-2 p-4 text-mute"><Loader2 size={14} className="animate-spin" /> Loading commit…</p>
  if (error) return <p role="alert" className="p-4 text-del">{error}</p>
  if (!data) return null

  return (
    <div className="flex h-full flex-col overflow-y-auto fade-in">
      <div className="space-y-3 border-b border-line p-3">
        <pre className="whitespace-pre-wrap break-words font-sans text-[13px]">{data.message}</pre>
        <dl>
          <Row label="SHA"><span className="select-all font-mono text-[11px]">{data.sha}</span></Row>
          <Row label="Author">{data.author} <span className="text-mute">&lt;{data.author_email}&gt;</span></Row>
          <Row label="Authored">{formatDateTime(data.author_date)}</Row>
          <Row label="Committed">{formatDateTime(data.commit_date)}
            {data.committer !== data.author && <span className="text-mute"> by {data.committer}</span>}</Row>
          <Row label={data.parents.length > 1 ? 'Parents' : 'Parent'}>
            {data.parents.length === 0 ? <span className="text-mute">none (root commit)</span> : (
              <span className="flex flex-wrap gap-2">
                {data.parents.map((p, i) => (
                  <button key={p} onClick={() => onSelect(p)} title={i === 0 ? 'First parent' : 'Merged-in parent'}
                    className="rounded border border-line px-1.5 font-mono text-[11px] text-accent hover:border-accent">
                    {p.slice(0, 7)}{data.parents.length > 1 && i === 0 ? ' (first)' : ''}
                  </button>
                ))}
              </span>
            )}
          </Row>
        </dl>
      </div>

      <div className="border-b border-line p-3">
        <div className="mb-1 flex items-baseline justify-between">
          <h3 className="font-semibold">{data.files.length}{data.files_truncated ? '+' : ''} changed files</h3>
          <span className="font-mono text-[11px]"><span className="text-add">+{data.total_additions}</span>{' '}
            <span className="text-del">−{data.total_deletions}</span></span>
        </div>
        <p className="mb-2 text-[11px] text-mute">{data.diff_base_note}</p>
        <ul>
          {data.files.map((f) => {
            const [letter, color] = statusStyle[f.status]
            return (
              <li key={f.path}>
                <button onClick={() => setFile(file === f.path ? null : f.path)} aria-pressed={file === f.path}
                  className={`flex w-full items-center gap-2 rounded px-1.5 py-1 text-left hover:bg-raised ${file === f.path ? 'bg-raised' : ''}`}>
                  <span className={`w-4 shrink-0 font-mono font-bold ${color}`} title={f.status}>{letter}</span>
                  <span className="min-w-0 flex-1 truncate font-mono text-[12px]" title={f.old_path ? `${f.old_path} → ${f.path}` : f.path}>
                    {f.old_path ? `${f.old_path} → ` : ''}{f.path}
                  </span>
                  <span className="shrink-0 font-mono text-[11px]">
                    {f.binary ? <span className="text-mute">binary</span> : <>
                      <span className="text-add">+{f.additions ?? 0}</span> <span className="text-del">−{f.deletions ?? 0}</span></>}
                  </span>
                </button>
                {file === f.path && (
                  <div className="my-1 overflow-hidden rounded border border-line bg-bg"><FileDiff sha={data.sha} path={f.path} /></div>
                )}
              </li>
            )
          })}
        </ul>
        {data.files_truncated && <p className="mt-2 text-warn">File list truncated to the first 500 files.</p>}
        {data.files.length === 0 && <p className="text-mute">No file changes (empty commit).</p>}
      </div>
    </div>
  )
}
