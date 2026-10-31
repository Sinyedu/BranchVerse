import { Loader2 } from 'lucide-react'
import { useAsync } from '../../hooks/useAsync'
import { api } from '../../services/api'

const lineClass = (line: string): string => {
  if (line.startsWith('+++') || line.startsWith('---')) return 'text-mute'
  if (line.startsWith('+')) return 'bg-add/10 text-add'
  if (line.startsWith('-')) return 'bg-del/10 text-del'
  if (line.startsWith('@@')) return 'text-accent'
  return 'text-ink/80'
}

/** Renders a unified diff as plain text (React escapes everything; no HTML injection). */
export function FileDiff({ sha, path }: { sha: string; path: string }) {
  const { data, error, loading } = useAsync((s) => api.diff(sha, path, s), [sha, path])

  if (loading) return <p className="flex items-center gap-2 p-3 text-mute"><Loader2 size={14} className="animate-spin" /> Loading diff…</p>
  if (error) return <p role="alert" className="p-3 text-del">{error}</p>
  if (!data) return null
  if (data.binary) return <p className="p-3 text-mute">Binary file — no text diff available.</p>
  if (!data.diff.trim()) return <p className="p-3 text-mute">No textual changes (mode or rename only).</p>

  return (
    <div>
      <pre className="overflow-x-auto py-2 font-mono text-[12px] leading-5">
        {data.diff.split('\n').map((line, i) => (
          <div key={i} className={`whitespace-pre px-3 ${lineClass(line)}`}>{line || ' '}</div>
        ))}
      </pre>
      {data.truncated && (
        <p className="border-t border-line bg-warn/10 px-3 py-2 text-warn">
          Large diff truncated — only the first 200 KB is shown.
        </p>
      )}
    </div>
  )
}
