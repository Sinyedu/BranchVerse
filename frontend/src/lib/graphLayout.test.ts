import { describe, expect, it } from 'vitest'
import { layoutGraph, type LayoutCommit } from './graphLayout'

const c = (sha: string, ...parents: string[]): LayoutCommit => ({ sha, parents })
const cols = (commits: LayoutCommit[]) => layoutGraph(commits).rows.map((r) => r.col)

describe('layoutGraph', () => {
  it('keeps a linear history in one lane with one edge per step', () => {
    const l = layoutGraph([c('c', 'b'), c('b', 'a'), c('a')])
    expect(l.rows.map((r) => r.col)).toEqual([0, 0, 0])
    expect(l.edges).toHaveLength(2)
    expect(l.edges.every((e) => e.fromCol === 0 && e.toCol === 0)).toBe(true)
    expect(l.continuations).toEqual([])
    expect(l.laneCount).toBe(1)
  })

  it('puts diverging branch tips in separate lanes and converges at the fork point', () => {
    // m and f are both children of base
    const l = layoutGraph([c('m', 'base'), c('f', 'base'), c('base')])
    expect(l.rows.map((r) => r.col)).toEqual([0, 1, 0])
    const into = l.edges.filter((e) => e.toRow === 2)
    expect(into.map((e) => [e.fromCol, e.toCol]).sort()).toEqual([[0, 0], [1, 0]])
    expect(l.laneCount).toBe(2)
  })

  it('draws a merge commit with an edge to each parent', () => {
    // M merges main-line B1 and feature F1; both descend from A
    const commits = [c('M', 'B1', 'F1'), c('F1', 'A'), c('B1', 'A'), c('A')]
    const l = layoutGraph(commits)
    expect(l.rows.map((r) => r.col)).toEqual([0, 1, 0, 0])
    const fromMerge = l.edges.filter((e) => e.fromRow === 0)
    expect(fromMerge.map((e) => e.toCol).sort()).toEqual([0, 1])
    expect(fromMerge.every((e) => e.fromCol === 0)).toBe(true) // fan out from the merge node
  })

  it('reuses a lane that already waits for the second parent', () => {
    const l = layoutGraph([c('X', 'P'), c('M', 'Q', 'P'), c('Q', 'P'), c('P')])
    expect(l.laneCount).toBeLessThanOrEqual(3)
    expect(l.rows[3].col).toBe(0)
  })

  it('handles root commits and frees their lane for reuse', () => {
    const l = layoutGraph([c('r1'), c('r2')])
    expect(l.rows.map((r) => r.col)).toEqual([0, 0])
    expect(l.edges).toHaveLength(0)
    expect(l.continuations).toEqual([])
  })

  it('reports a continuation, not a false edge, for a parent outside the page', () => {
    const l = layoutGraph([c('b', 'a'), c('a', 'missing')])
    expect(l.continuations).toEqual([{ row: 1, col: 0 }])
    expect(l.edges).toHaveLength(1) // only b -> a is real
  })

  it('reports every dangling lane at the page boundary', () => {
    const l = layoutGraph([c('M', 'x', 'y')])
    expect(l.continuations.map((k) => k.col).sort()).toEqual([0, 0])
    expect(l.laneCount).toBe(2)
  })

  it('is prefix-stable when more history is loaded', () => {
    const all = [c('M', 'B1', 'F1'), c('F1', 'A'), c('B1', 'A'), c('A', 'Z'), c('Z')]
    const partial = layoutGraph(all.slice(0, 3))
    const full = layoutGraph(all)
    expect(full.rows.slice(0, 3)).toEqual(partial.rows)
    const inner = (e: { toRow: number }) => e.toRow <= 2
    expect(full.edges.filter(inner)).toEqual(partial.edges.filter(inner))
  })

  it('returns an empty layout for no commits', () => {
    expect(cols([])).toEqual([])
  })

  it('never lets two commits in the same row share a column with a different commit', () => {
    const l = layoutGraph([c('a', 'p'), c('b', 'p'), c('d', 'p'), c('p')])
    expect(new Set(l.rows.slice(0, 3).map((r) => r.col)).size).toBe(3)
  })
})
