import { describe, expect, it } from 'vitest'
import { layoutGraph } from './graphLayout'
import { edgeSlice, scrollToRow, visibleRange } from './virtual'

describe('visibleRange', () => {
  it('returns the viewport rows plus overscan, clamped to the list', () => {
    expect(visibleRange(0, 400, 40, 1000, 5)).toEqual({ start: 0, end: 15 })
    expect(visibleRange(4000, 400, 40, 1000, 5)).toEqual({ start: 95, end: 115 })
    expect(visibleRange(39_000, 400, 40, 1000, 5)).toEqual({ start: 970, end: 990 })
  })
  it('is empty for no rows and tolerates a zero-height viewport', () => {
    expect(visibleRange(0, 400, 40, 0)).toEqual({ start: 0, end: 0 })
    expect(visibleRange(0, 0, 40, 100, 0).end).toBe(1)
    expect(visibleRange(-50, 400, 40, 100, 0).start).toBe(0)
  })
})

describe('edgeSlice', () => {
  it('selects exactly the edges touching the window', () => {
    const commits = Array.from({ length: 50 }, (_, i) => ({ sha: `c${i}`, parents: i < 49 ? [`c${i + 1}`] : [] }))
    const { edges } = layoutGraph(commits)
    const [a, b] = edgeSlice(edges, { start: 10, end: 20 })
    const picked = edges.slice(a, b)
    expect(picked.every((e) => e.toRow >= 10 && e.fromRow <= 19)).toBe(true)
    const outside = [...edges.slice(0, a), ...edges.slice(b)]
    expect(outside.every((e) => e.toRow < 10 || e.fromRow >= 20)).toBe(true)
  })
  it('handles an empty edge list', () => {
    expect(edgeSlice([], { start: 0, end: 10 })).toEqual([0, 0])
  })
})

describe('scrollToRow', () => {
  it('only scrolls when the row is outside the viewport', () => {
    expect(scrollToRow(5, 40, 0, 400)).toBeNull()
    expect(scrollToRow(20, 40, 0, 400)).toBe(440)
    expect(scrollToRow(2, 40, 400, 400)).toBe(80)
  })
})
