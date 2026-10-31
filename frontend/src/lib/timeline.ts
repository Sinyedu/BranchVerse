/** Pure helpers for Time Machine navigation (oldest-first index, newest = last). */

export const clampIndex = (i: number, length: number): number =>
  length === 0 ? 0 : Math.min(Math.max(Math.round(i), 0), length - 1)

export const presentIndex = (length: number): number => Math.max(length - 1, 0)

export const stepIndex = (i: number, delta: number, length: number): number =>
  clampIndex(i + delta, length)

export const isPresent = (i: number, length: number): boolean => i === presentIndex(length)

/** Index of the snapshot with this SHA, or the present if it is unknown. */
export function indexOfSha(shas: string[], sha: string | null): number {
  const i = sha ? shas.indexOf(sha) : -1
  return i >= 0 ? i : presentIndex(shas.length)
}
