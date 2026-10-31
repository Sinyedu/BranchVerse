import type { Release } from '../types/git'

/** Median of the known gaps (in days) between consecutive releases, or null if there are none. */
export function medianInterval(releases: Release[]): number | null {
  const gaps = releases.map((r) => r.days_since_previous).filter((d): d is number => d !== null).sort((a, b) => a - b)
  if (gaps.length === 0) return null
  const mid = Math.floor(gaps.length / 2)
  return gaps.length % 2 ? gaps[mid] : (gaps[mid - 1] + gaps[mid]) / 2
}

/** Bar width as a 0–100 percentage of the largest commit count; unknown counts get no bar. */
export function barPercent(commits: number | null, releases: Release[]): number {
  if (commits === null) return 0
  const max = Math.max(...releases.map((r) => r.commits ?? 0), 1)
  return Math.max(Math.round((commits / max) * 100), commits > 0 ? 2 : 0)
}

export function formatInterval(days: number | null): string {
  if (days === null) return '—'
  if (days < 1) return '<1 day'
  return days === 1 ? '1 day' : `${Number.isInteger(days) ? days : days.toFixed(1)} days`
}
