/** Accepts "123", "#123", or a github.com/.../pull/123 link; returns the number or null. */
export function parsePullNumber(input: string): number | null {
  const text = input.trim()
  const m = /^#?(\d{1,8})$/.exec(text) ?? /^(?:https?:\/\/)?github\.com\/[^/\s]+\/[^/\s]+\/pull\/(\d{1,8})(?:[/?#]\S*)?$/i.exec(text)
  if (!m) return null
  const n = Number(m[1])
  return n >= 1 && n <= 10_000_000 ? n : null
}
