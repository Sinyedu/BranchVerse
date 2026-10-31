import { GitMerge } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { relativeTime } from '../../lib/formatters'
import type { Compare, FileChange, FileDiff as FileDiffData } from '../../types/git'
import { FileDiff } from '../commits/FileDiff'

const letter: Record<FileChange['status'], [string, string]> = {
  added: ['A', 'text-add'], modified: ['M', 'text-warn'], deleted: ['D', 'text-del'],
  renamed: ['R', 'text-accent'], copied: ['C', 'text-accent'], other: ['?', 'text-mute'],
}

interface Props {
  c: Compare
  loadDiff: (path: string, signal: AbortSignal) => Promise<FileDiffData>
  summary?: ReactNode
}

/** Commits + changed files + expandable diffs: the body shared by branch compare and pull requests. */
export function ComparisonResult({ c, loadDiff, summary }: Props) {
  const [openFile, setOpenFile] = useState<string | null>(null)
  return (
    <div className="mt-5 max-w-4xl fade-in">
      <section className="rounded-lg border border-line bg-panel p-4">
        {summary ?? (
          <p className="flex flex-wrap items-center gap-2 text-[15px]">
            <GitMerge size={16} className="text-accent" />
            <b className="font-mono">{c.head}</b> <span className="text-mute">would merge into</span> <b className="font-mono">{c.base}</b>
          </p>
        )}
        <p className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
          <span><b>{c.ahead}</b> <span className="text-mute">commit{c.ahead === 1 ? '' : 's'} ahead</span></span>
          <span><b>{c.behind}</b> <span className="text-mute">behind</span></span>
          <span><b>{c.files.length}{c.files_truncated ? '+' : ''}</b> <span className="text-mute">files changed</span></span>
          <span className="font-mono"><span className="text-add">+{c.total_additions}</span> <span className="text-del">−{c.total_deletions}</span></span>
        </p>
        <p className="mt-2 text-[12px] text-mute">{c.note}</p>
      </section>

      <h3 className="mb-1 mt-5 font-semibold">Commits <span className="font-normal text-mute">({c.ahead})</span></h3>
      {c.commits.length === 0 ? <p className="text-mute">No commits to show.</p> : (
        <ul className="divide-y divide-line rounded-lg border border-line bg-panel">
          {c.commits.map((k) => (
            <li key={k.sha} className="flex items-center gap-3 px-3 py-1.5">
              <span className="min-w-0 flex-1 truncate" title={k.subject}>{k.subject}</span>
              <span className="hidden text-mute md:block">{k.author}</span>
              <span className="w-16 text-right text-mute">{relativeTime(k.timestamp)}</span>
              <span className="font-mono text-[11px] text-mute">{k.short_sha}</span>
            </li>
          ))}
        </ul>
      )}
      {c.commits_truncated && <p className="mt-1 text-warn">Showing the first 100 commits.</p>}

      <h3 className="mb-1 mt-5 font-semibold">Files changed</h3>
      {c.files.length === 0 ? <p className="text-mute">No file changes.</p> : (
        <ul className="rounded-lg border border-line bg-panel">
          {c.files.map((f) => {
            const [l, color] = letter[f.status]
            const open = openFile === f.path
            return (
              <li key={f.path} className="border-b border-line last:border-b-0">
                <button onClick={() => setOpenFile(open ? null : f.path)} aria-expanded={open}
                  className={`flex w-full items-center gap-3 px-3 py-1.5 text-left hover:bg-raised ${open ? 'bg-raised' : ''}`}>
                  <span className={`w-4 font-mono font-bold ${color}`} title={f.status}>{l}</span>
                  <span className="min-w-0 flex-1 truncate font-mono text-[12px]">{f.old_path ? `${f.old_path} → ` : ''}{f.path}</span>
                  <span className="font-mono text-[11px]">{f.binary ? <span className="text-mute">binary</span> : <>
                    <span className="text-add">+{f.additions ?? 0}</span> <span className="text-del">−{f.deletions ?? 0}</span></>}</span>
                </button>
                {open && (
                  <div className="overflow-hidden border-t border-line bg-bg">
                    <FileDiff cacheKey={`${c.base_sha}:${c.head_sha}:${f.path}`} load={(s) => loadDiff(f.path, s)} />
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
      {c.files_truncated && <p className="mt-1 text-warn">File list truncated to the first 500 files.</p>}
    </div>
  )
}
