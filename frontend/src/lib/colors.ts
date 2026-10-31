// Categorical hues in fixed order (dark-surface steps), validated with the dataviz palette checker.
export const LANE_COLORS = [
  '#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767',
]
export const laneColor = (i: number): string => LANE_COLORS[i % LANE_COLORS.length]
export const SERIES_A = '#3987e5'
export const SERIES_B = '#d95926'
