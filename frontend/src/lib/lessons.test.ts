import { describe, expect, it } from 'vitest'
import { layoutGraph } from './graphLayout'
import { LESSONS, lessonCommits } from './lessons'

describe('lessons', () => {
  it('only reference parents that appear earlier in the node list', () => {
    for (const lesson of LESSONS) {
      const seen = new Set<string>()
      for (const node of lesson.nodes) {
        for (const p of node.parents) expect(seen.has(p), `${lesson.id}:${node.id}`).toBe(true)
        seen.add(node.id)
      }
    }
  })

  it('every step shows a consistent, fully connected graph', () => {
    for (const lesson of LESSONS) {
      lesson.steps.forEach((_, i) => {
        const commits = lessonCommits(lesson, i)
        expect(layoutGraph(commits).continuations, `${lesson.id} step ${i}`).toEqual([])
      })
    }
  })

  it('labels only point at commits that are visible in that step', () => {
    for (const lesson of LESSONS) {
      for (const step of lesson.steps) {
        const visible = new Set(lesson.nodes.slice(0, step.count).map((x) => x.id))
        for (const id of Object.keys(step.refs)) expect(visible.has(id), `${lesson.id}:${id}`).toBe(true)
      }
    }
  })

  it('returns newest first', () => {
    const lesson = LESSONS[0]
    const commits = lessonCommits(lesson, lesson.steps.length - 1)
    expect(commits[0].sha).toBe('c9d04ab')
    expect(commits.at(-1)?.parents).toEqual([])
  })
})
