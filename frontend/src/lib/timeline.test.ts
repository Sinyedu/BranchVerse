import { describe, expect, it } from 'vitest'
import { clampIndex, indexOfSha, isPresent, presentIndex, stepIndex } from './timeline'

describe('timeline selection', () => {
  it('clamps to the valid range', () => {
    expect(clampIndex(-3, 5)).toBe(0)
    expect(clampIndex(9, 5)).toBe(4)
    expect(clampIndex(2.6, 5)).toBe(3)
    expect(clampIndex(1, 0)).toBe(0)
  })
  it('treats the last (newest) snapshot as the present', () => {
    expect(presentIndex(5)).toBe(4)
    expect(isPresent(4, 5)).toBe(true)
    expect(isPresent(3, 5)).toBe(false)
  })
  it('steps backwards and forwards without leaving the range', () => {
    expect(stepIndex(0, -1, 5)).toBe(0)
    expect(stepIndex(4, 1, 5)).toBe(4)
    expect(stepIndex(2, -1, 5)).toBe(1)
  })
  it('finds a sha or falls back to the present', () => {
    expect(indexOfSha(['a', 'b', 'c'], 'b')).toBe(1)
    expect(indexOfSha(['a', 'b', 'c'], 'zzz')).toBe(2)
    expect(indexOfSha(['a', 'b', 'c'], null)).toBe(2)
  })
})
