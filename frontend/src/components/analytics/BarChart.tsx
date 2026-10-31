import { useState } from 'react'
import type { WeekBucket } from '../../types/git'

export interface Series { key: 'commits' | 'additions' | 'deletions'; label: string; color: string }

interface Props {
  title: string
  data: WeekBucket[]
  series: Series[]
  emptyText: string
}

const H = 150, TOP = 8, BOTTOM = 20, LEFT = 40

/** Weekly bar chart. >1 series -> grouped bars with a legend; every bar has a hover tooltip. */
export function BarChart({ title, data, series, emptyText }: Props) {
  const [hover, setHover] = useState<number | null>(null)
  const max = Math.max(1, ...data.flatMap((d) => series.map((s) => d[s.key])))
  const slot = Math.max(6, Math.min(28, 640 / Math.max(data.length, 1)))
  const width = LEFT + data.length * slot + 8
  const plotH = H - TOP - BOTTOM
  const barW = Math.max(2, (slot - 3) / series.length - 2)

  if (data.length === 0 || data.every((d) => series.every((s) => d[s.key] === 0))) {
    return <p className="rounded border border-line bg-panel p-4 text-mute">{emptyText}</p>
  }
  const hovered = hover !== null ? data[hover] : null

  return (
    <figure className="rounded-lg border border-line bg-panel p-4">
      <figcaption className="mb-2 flex flex-wrap items-baseline gap-x-4">
        <span className="font-semibold">{title}</span>
        {series.length > 1 && series.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5 text-mute">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />{s.label}
          </span>
        ))}
        <span className="ml-auto h-4 text-mute">
          {hovered && <>Week of {hovered.week_start}: {series.map((s) => `${hovered[s.key].toLocaleString()} ${s.label.toLowerCase()}`).join(' · ')}</>}
        </span>
      </figcaption>
      <div className="overflow-x-auto">
        <svg width={width} height={H} role="img" aria-label={`${title}, ${data.length} weeks`}>
          {[0, 0.5, 1].map((t) => (
            <g key={t}>
              <line x1={LEFT} x2={width} y1={TOP + plotH * (1 - t)} y2={TOP + plotH * (1 - t)} stroke="#2a2f37" strokeWidth={1} />
              <text x={LEFT - 6} y={TOP + plotH * (1 - t) + 4} textAnchor="end" fontSize={10} fill="#8b93a1">
                {Math.round(max * t).toLocaleString()}
              </text>
            </g>
          ))}
          {data.map((d, i) => (
            <g key={d.week_start} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={LEFT + i * slot} y={TOP} width={slot} height={plotH} fill="transparent" />
              {series.map((s, j) => {
                const h = (d[s.key] / max) * plotH
                return <rect key={s.key} x={LEFT + i * slot + 1.5 + j * (barW + 2)} y={TOP + plotH - h}
                  width={barW} height={h} rx={Math.min(2, barW / 2)} fill={s.color} opacity={hover === null || hover === i ? 1 : 0.5} />
              })}
            </g>
          ))}
          <text x={LEFT} y={H - 4} fontSize={10} fill="#8b93a1">{data[0].week_start}</text>
          <text x={width - 8} y={H - 4} fontSize={10} fill="#8b93a1" textAnchor="end">{data[data.length - 1].week_start}</text>
        </svg>
      </div>
      <details className="mt-2 text-mute">
        <summary className="cursor-pointer">View as table</summary>
        <table className="mt-2 w-full max-w-md text-left">
          <thead><tr><th className="font-normal">Week</th>{series.map((s) => <th key={s.key} className="text-right font-normal">{s.label}</th>)}</tr></thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.week_start}><td>{d.week_start}</td>{series.map((s) => <td key={s.key} className="text-right font-mono">{d[s.key]}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  )
}
