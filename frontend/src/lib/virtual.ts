/** Windowing helpers so only the rows near the viewport are rendered. */

export interface Range { start: number; end: number } // end is exclusive

export function visibleRange(
  scrollTop: number, viewport: number, rowH: number, total: number, overscan = 10,
): Range {
  if (total <= 0) return { start: 0, end: 0 }
  const first = Math.floor(Math.max(scrollTop, 0) / rowH)
  const last = Math.ceil((Math.max(scrollTop, 0) + Math.max(viewport, rowH)) / rowH)
  return { start: Math.max(0, first - overscan), end: Math.min(total, last + overscan) }
}

const lowerBound = (edges: { toRow: number }[], row: number): number => {
  let lo = 0, hi = edges.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (edges[mid].toRow < row) lo = mid + 1
    else hi = mid
  }
  return lo
}

/**
 * Edges are produced in ascending `toRow` order. Returns the index slice of edges
 * that touch rows [start, end): each edge spans rows toRow-1 .. toRow.
 */
export function edgeSlice(edges: { toRow: number }[], range: Range): [number, number] {
  return [lowerBound(edges, range.start), lowerBound(edges, range.end + 1)]
}

/** New scrollTop that brings row `index` fully into view, or null if it already is. */
export function scrollToRow(index: number, rowH: number, scrollTop: number, viewport: number): number | null {
  const top = index * rowH
  if (top < scrollTop) return top
  if (top + rowH > scrollTop + viewport) return top + rowH - viewport
  return null
}
