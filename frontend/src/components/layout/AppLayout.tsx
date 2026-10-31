import { FolderOpen, GitBranch } from 'lucide-react'
import type { ReactNode } from 'react'
import { APP_NAME, plural } from '../../lib/formatters'
import type { RepositoryInfo } from '../../types/git'
import { Sidebar, type View } from './Sidebar'

interface Props {
  repo: RepositoryInfo | null
  commitCount: number
  hasMore: boolean
  view: View
  onView: (v: View) => void
  onSwitchRepo: () => void
  inspector: ReactNode | null
  children: ReactNode
}

export function AppLayout({ repo, commitCount, hasMore, view, onView, onSwitchRepo, inspector, children }: Props) {
  const branchLabel = !repo ? null : repo.is_detached ? `detached at ${repo.head_sha?.slice(0, 7)}` : (repo.current_branch ?? 'no branch yet')
  return (
    <div className="flex h-full flex-col">
      <header className="flex h-11 shrink-0 items-center gap-4 border-b border-line bg-panel px-4">
        <span className="flex items-center gap-2 font-semibold"><GitBranch size={16} className="text-accent" />{APP_NAME}</span>
        {repo && <span className="truncate text-mute" title={repo.remote_url ?? repo.path}>
          {repo.remote_url ? repo.remote_url.replace('https://github.com/', '').replace(/\.git$/, '') : repo.name}</span>}
        <button onClick={onSwitchRepo} className="ml-auto flex items-center gap-1.5 rounded border border-line px-2.5 py-1 hover:border-accent">
          <FolderOpen size={14} /> {repo ? 'Open another repository' : 'Open Repository'}
        </button>
      </header>
      <div className="flex min-h-0 flex-1">
        <Sidebar view={view} hasRepo={repo !== null} onChange={onView} />
        <main className="min-w-0 flex-1 bg-bg">{children}</main>
        {inspector && <aside aria-label="Commit inspector" className="w-[26rem] shrink-0 border-l border-line bg-panel">{inspector}</aside>}
      </div>
      <footer className="flex h-7 shrink-0 items-center gap-4 border-t border-line bg-panel px-4 text-[12px] text-mute">
        {repo ? (
          <>
            <span>Read-only{repo.remote_url ? ' · GitHub download (temporary copy)' : ''}</span>
            <span>Branch: <span className="text-ink">{branchLabel}</span></span>
            {repo.is_bare && <span>bare repository</span>}
            {repo.is_empty ? <span>Empty repository</span> : <span>{plural(commitCount, 'commit')} loaded{hasMore ? ' (more available)' : ''}</span>}
          </>
        ) : <span>No repository open</span>}
      </footer>
    </div>
  )
}
