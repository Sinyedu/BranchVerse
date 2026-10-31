import { BarChart3, BookOpen, GitBranch, GitCommitHorizontal, GitPullRequest, History, Network, Tag } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type View = 'graph' | 'branches' | 'compare' | 'strategy' | 'analytics' | 'time' | 'releases' | 'learn'

const ITEMS: { id: View; label: string; icon: LucideIcon; needsRepo: boolean }[] = [
  { id: 'graph', label: 'Commits', icon: GitCommitHorizontal, needsRepo: true },
  { id: 'branches', label: 'Branches', icon: GitBranch, needsRepo: true },
  { id: 'compare', label: 'Compare', icon: GitPullRequest, needsRepo: true },
  { id: 'strategy', label: 'Strategy', icon: Network, needsRepo: true },
  { id: 'analytics', label: 'Analytics', icon: BarChart3, needsRepo: true },
  { id: 'time', label: 'Time Machine', icon: History, needsRepo: true },
  { id: 'releases', label: 'Releases', icon: Tag, needsRepo: true },
  { id: 'learn', label: 'Learn', icon: BookOpen, needsRepo: false },
]

interface Props { view: View; hasRepo: boolean; onChange: (v: View) => void }

export function Sidebar({ view, hasRepo, onChange }: Props) {
  return (
    <nav aria-label="Views" className="flex w-44 shrink-0 flex-col gap-0.5 border-r border-line bg-panel p-2">
      {ITEMS.map(({ id, label, icon: Icon, needsRepo }) => {
        const disabled = needsRepo && !hasRepo
        return (
          <button key={id} disabled={disabled} onClick={() => onChange(id)} aria-current={view === id ? 'page' : undefined}
            title={disabled ? 'Open a repository first' : undefined}
            className={`flex items-center gap-2.5 rounded px-2.5 py-2 text-left hover:bg-raised disabled:opacity-35 disabled:hover:bg-transparent ${
              view === id ? 'bg-raised text-accent' : ''}`}>
            <Icon size={16} aria-hidden /> {label}
          </button>
        )
      })}
    </nav>
  )
}
