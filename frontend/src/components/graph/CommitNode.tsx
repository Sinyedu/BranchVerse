import { Tag } from 'lucide-react'
import { memo } from 'react'
import { relativeTime } from '../../lib/formatters'
import type { Commit, RefLabel } from '../../types/git'
import { ROW_H } from './GraphEdges'

const chip: Record<RefLabel['kind'], string> = {
  head: 'bg-accent/20 text-accent border-accent/50',
  branch: 'bg-add/10 text-add border-add/40',
  remote: 'bg-raised text-mute border-line',
  tag: 'bg-warn/10 text-warn border-warn/40',
}

interface Props {
  commit: Commit
  row: number
  paddingLeft: number
  selected: boolean
  dimmed: boolean
  onSelect: (sha: string) => void
  onHover: (sha: string | null) => void
}

/** One text row of the graph (the node itself is drawn in the shared SVG). Memoised: hovering only re-renders changed rows. */
export const CommitNode = memo(function CommitNode({ commit, row, paddingLeft, selected, dimmed, onSelect, onHover }: Props) {
  return (
    <button
      id={`row-${commit.sha}`}
      type="button"
      onClick={() => onSelect(commit.sha)}
      onMouseEnter={() => onHover(commit.sha)}
      onMouseLeave={() => onHover(null)}
      aria-pressed={selected}
      style={{ position: 'absolute', top: row * ROW_H, left: 0, right: 0, height: ROW_H, paddingLeft }}
      className={`flex items-center gap-3 pr-3 text-left transition-colors hover:bg-raised/70 ${
        selected ? 'bg-raised' : ''} ${dimmed ? 'opacity-35' : ''}`}
    >
      <span className="flex min-w-0 flex-1 items-center gap-2">
        {commit.refs.map((r) => (
          <span key={r.kind + r.name}
            className={`inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-px text-[11px] ${chip[r.kind]}`}>
            {r.kind === 'tag' && <Tag size={10} aria-hidden />}
            {r.name}
          </span>
        ))}
        <span className="truncate" title={commit.subject}>{commit.subject || '(no subject)'}</span>
      </span>
      <span className="hidden w-32 shrink-0 truncate text-mute lg:block" title={commit.email}>{commit.author}</span>
      <span className="hidden w-16 shrink-0 text-right text-mute md:block">{relativeTime(commit.timestamp)}</span>
      <span className="w-14 shrink-0 font-mono text-[11px] text-mute">{commit.short_sha}</span>
    </button>
  )
})
