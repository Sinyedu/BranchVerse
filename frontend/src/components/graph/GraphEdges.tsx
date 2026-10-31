import { laneColor } from '../../lib/colors'
import type { GraphLayout } from '../../lib/graphLayout'
import { edgeSlice, type Range } from '../../lib/virtual'
import type { Commit } from '../../types/git'

export const ROW_H = 40
export const LANE_W = 18
export const PAD = 14

export const xOf = (col: number) => PAD + col * LANE_W
export const yOf = (row: number) => row * ROW_H + ROW_H / 2

interface Props {
  layout: GraphLayout
  commits: Commit[]
  range: Range
  selected: string | null
  dim: (sha: string) => boolean
  hovered: string | null
  hasMore: boolean
}

/** One SVG for the whole graph, but only the edges and nodes in `range` are drawn. */
export function GraphEdges({ layout, commits, range, selected, dim, hovered, hasMore }: Props) {
  const width = PAD * 2 + layout.laneCount * LANE_W
  const height = commits.length * ROW_H + (hasMore ? ROW_H : 0)
  const [from, to] = edgeSlice(layout.edges, range)
  const edges = layout.edges.slice(from, to)
  const rows = layout.rows.slice(range.start, range.end)
  const lastRow = commits.length - 1

  return (
    <svg width={width} height={height} className="pointer-events-none absolute left-0 top-0" aria-hidden="true">
      {edges.map((e, i) => {
        const x1 = xOf(e.fromCol), y1 = yOf(e.fromRow), x2 = xOf(e.toCol), y2 = yOf(e.toRow)
        const mid = (y1 + y2) / 2
        const d = x1 === x2 ? `M${x1} ${y1}L${x2} ${y2}` : `M${x1} ${y1}C${x1} ${mid} ${x2} ${mid} ${x2} ${y2}`
        const faded = dim(commits[e.fromRow].sha) || dim(commits[e.toRow].sha)
        return <path key={from + i} d={d} fill="none" stroke={laneColor(e.lane)} strokeWidth={2}
          opacity={faded ? 0.15 : 1} />
      })}
      {range.end > lastRow && layout.continuations.map((k, i) => (
        <path key={`c${i}`} d={`M${xOf(k.col)} ${yOf(k.row)}L${xOf(k.col)} ${yOf(k.row) + ROW_H * 0.7}`}
          stroke={laneColor(k.col)} strokeWidth={2} strokeDasharray="3 4" fill="none" opacity={0.8} />
      ))}
      {rows.map((r) => {
        const commit = commits[r.row]
        const color = laneColor(r.col)
        const isSel = commit.sha === selected
        return (
          <g key={commit.sha} opacity={dim(commit.sha) ? 0.25 : 1}>
            {(isSel || hovered === commit.sha) && (
              <circle cx={xOf(r.col)} cy={yOf(r.row)} r={9} fill="none"
                stroke={isSel ? '#e6e8eb' : color} strokeWidth={2} opacity={isSel ? 1 : 0.5} />
            )}
            <circle cx={xOf(r.col)} cy={yOf(r.row)} r={5} fill={commit.parents.length > 1 ? '#111317' : color}
              stroke={color} strokeWidth={2} />
          </g>
        )
      })}
    </svg>
  )
}
