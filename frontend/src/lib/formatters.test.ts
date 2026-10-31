import { describe, expect, it } from 'vitest'
import { plural, relativeTime } from './formatters'

describe('formatters', () => {
  it('formats relative times', () => {
    const now = 1_000_000_000
    expect(relativeTime(now - 5, now)).toBe('just now')
    expect(relativeTime(now - 120, now)).toBe('2m ago')
    expect(relativeTime(now - 3 * 3600, now)).toBe('3h ago')
    expect(relativeTime(now - 2 * 86400, now)).toBe('2d ago')
    expect(relativeTime(now - 400 * 86400, now)).toBe('1y ago')
    expect(relativeTime(now + 100, now)).toBe('just now')
  })
  it('pluralizes', () => {
    expect(plural(1, 'commit')).toBe('1 commit')
    expect(plural(1200, 'commit')).toBe('1,200 commits')
  })
})
