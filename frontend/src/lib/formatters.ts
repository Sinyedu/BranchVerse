export const APP_NAME = 'BranchVerse'

export function formatDate(ts: number | null): string {
  if (ts === null) return '—'
  return new Date(ts * 1000).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function relativeTime(ts: number, now = Date.now() / 1000): string {
  const s = Math.max(0, Math.round(now - ts))
  const units: [number, string][] = [[31536000, 'y'], [2592000, 'mo'], [604800, 'w'], [86400, 'd'], [3600, 'h'], [60, 'm']]
  for (const [size, label] of units) if (s >= size) return `${Math.floor(s / size)}${label} ago`
  return 'just now'
}

export function plural(n: number, word: string): string {
  return `${n.toLocaleString()} ${word}${n === 1 ? '' : 's'}`
}
