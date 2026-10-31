/**
 * Lane-allocation layout for a commit DAG.
 *
 * Input: commits in topological order (children before parents, newest first).
 * Each lane is "waiting" for one commit SHA: the next commit its line must reach.
 *   1. A commit takes the left-most lane waiting for it (or a fresh lane = branch tip).
 *   2. Other lanes waiting for the same SHA converge into it and are freed.
 *   3. Its first parent continues in the same lane; extra parents (merges) join
 *      a lane already waiting for them, or get a new lane.
 *   4. Root commits free their lane.
 * Lanes still waiting after the last row point to commits outside the loaded
 * page, so they are reported as `continuations` instead of drawing a false edge.
 * Layout is prefix-stable: loading more history never moves earlier rows.
 */
export interface LayoutCommit { sha: string; parents: string[] }
export interface LayoutRow { sha: string; row: number; col: number }
export interface Edge { fromRow: number; fromCol: number; toRow: number; toCol: number; lane: number }
export interface Continuation { row: number; col: number }
export interface GraphLayout {
  rows: LayoutRow[]
  edges: Edge[]
  continuations: Continuation[]
  laneCount: number
}

export function layoutGraph(commits: LayoutCommit[]): GraphLayout {
  const lanes: (string | null)[] = []
  const origin: number[] = [] // column each lane's line leaves from on the previous row
  const rows: LayoutRow[] = []
  const edges: Edge[] = []
  let laneCount = 0

  const freeLane = (): number => {
    const i = lanes.indexOf(null)
    if (i >= 0) return i
    lanes.push(null)
    origin.push(lanes.length - 1)
    return lanes.length - 1
  }

  commits.forEach((commit, row) => {
    const waiting = lanes.flatMap((s, i) => (s === commit.sha ? [i] : []))
    const col = waiting.length ? waiting[0] : freeLane()

    // Segments from the previous row into this one.
    if (row > 0) {
      lanes.forEach((sha, lane) => {
        if (sha === null) return
        edges.push({
          fromRow: row - 1, fromCol: origin[lane], toRow: row,
          toCol: sha === commit.sha ? col : lane, lane,
        })
      })
    }
    waiting.forEach((i) => { lanes[i] = null })

    lanes.forEach((_, i) => { origin[i] = i })
    const [first, ...rest] = commit.parents
    if (first !== undefined) lanes[col] = first
    for (const parent of rest) {
      let lane = lanes.indexOf(parent)
      if (lane < 0) { lane = freeLane(); lanes[lane] = parent }
      origin[lane] = col // merge edge fans out from the commit's column
    }
    rows.push({ sha: commit.sha, row, col })
    laneCount = Math.max(laneCount, lanes.length, col + 1)
  })

  const continuations: Continuation[] = []
  if (commits.length > 0) {
    lanes.forEach((sha, lane) => {
      if (sha !== null) continuations.push({ row: commits.length - 1, col: origin[lane] })
    })
  }
  return { rows, edges, continuations, laneCount: Math.max(laneCount, 1) }
}
