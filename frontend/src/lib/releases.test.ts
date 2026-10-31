import { describe, expect, it } from 'vitest'
import type { Release } from '../types/git'
import { barPercent, formatInterval, medianInterval } from './releases'

const rel = (commits: number | null, days: number | null): Release => ({
  name: 'v', sha: 'a'.repeat(40), short_sha: 'aaaaaaa', timestamp: 0, annotated: false, message: null,
  previous: null, commits, contributors: null, days_since_previous: days,
})

describe('release helpers', () => {
  it('takes the median of known gaps', () => {
    expect(medianInterval([rel(1, null), rel(1, 4), rel(1, 10), rel(1, 2)])).toBe(4)
    expect(medianInterval([rel(1, 2), rel(1, 4)])).toBe(3)
    expect(medianInterval([rel(1, null)])).toBeNull()
    expect(medianInterval([])).toBeNull()
  })
  it('scales bars to the largest release', () => {
    const rs = [rel(10, 1), rel(5, 1), rel(null, 1), rel(0, 1)]
    expect(barPercent(10, rs)).toBe(100)
    expect(barPercent(5, rs)).toBe(50)
    expect(barPercent(null, rs)).toBe(0)
    expect(barPercent(0, rs)).toBe(0)
    expect(barPercent(1, [rel(1000, 1), rel(1, 1)])).toBe(2)
  })
  it('formats intervals', () => {
    expect(formatInterval(null)).toBe('—')
    expect(formatInterval(0.2)).toBe('<1 day')
    expect(formatInterval(1)).toBe('1 day')
    expect(formatInterval(5)).toBe('5 days')
    expect(formatInterval(2.5)).toBe('2.5 days')
  })
})
