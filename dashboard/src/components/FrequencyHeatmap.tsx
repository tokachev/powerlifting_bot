import { useMemo } from 'react'
import type { FrequencyResponse } from '@/api/types'
import { MUSCLE_GROUP_LABELS, MUSCLE_GROUPS } from '@/api/types'

interface Props {
  data: FrequencyResponse
}

function cellColor(sessions: number): string {
  if (sessions === 0) return 'rgba(255,255,255,0.04)'
  const t = Math.min(sessions / 4, 1)
  const alpha = 0.2 + t * 0.8
  return `rgba(59, 130, 246, ${alpha.toFixed(2)})`
}

const CELL_W = 48
const CELL_H = 28
const LABEL_W = 64
const GAP = 2

export function FrequencyHeatmap({ data }: Props) {
  const { grid, weeks, muscles } = useMemo(() => {
    const weekSet = new Set<string>()
    const muscleSet = new Set<string>()
    const map = new Map<string, number>()

    for (const c of data.cells) {
      weekSet.add(c.iso_week)
      muscleSet.add(c.muscle_group)
      map.set(`${c.iso_week}:${c.muscle_group}`, c.sessions)
    }

    const weeks = Array.from(weekSet).sort()
    const muscles = MUSCLE_GROUPS.filter((m) => muscleSet.has(m))
    return { grid: map, weeks, muscles }
  }, [data])

  if (weeks.length === 0) {
    return (
      <div className="glass-card">
        <h3 className="chart-title">Частота по мышцам</h3>
        <div className="text-neutral-500 text-sm py-8 text-center">Нет данных</div>
      </div>
    )
  }

  const svgWidth = LABEL_W + weeks.length * (CELL_W + GAP) + 4
  const svgHeight = 20 + muscles.length * (CELL_H + GAP) + 4

  return (
    <div className="glass-card">
      <h3 className="chart-title">Частота по мышцам (сессий/неделя)</h3>
      <div className="overflow-x-auto">
        <svg width={svgWidth} height={svgHeight}>
          {/* week headers */}
          {weeks.map((w, wi) => (
            <text
              key={w}
              x={LABEL_W + wi * (CELL_W + GAP) + CELL_W / 2}
              y={12}
              textAnchor="middle"
              fontSize={9}
              fill="rgba(255,255,255,0.3)"
            >
              {w.slice(5)}
            </text>
          ))}
          {/* rows */}
          {muscles.map((mg, mi) => (
            <g key={mg}>
              <text
                x={0}
                y={20 + mi * (CELL_H + GAP) + CELL_H / 2 + 4}
                fontSize={10}
                fill="rgba(255,255,255,0.5)"
              >
                {MUSCLE_GROUP_LABELS[mg] ?? mg}
              </text>
              {weeks.map((w, wi) => {
                const val = grid.get(`${w}:${mg}`) ?? 0
                return (
                  <g key={w}>
                    <rect
                      x={LABEL_W + wi * (CELL_W + GAP)}
                      y={20 + mi * (CELL_H + GAP)}
                      width={CELL_W}
                      height={CELL_H}
                      rx={4}
                      fill={cellColor(val)}
                    />
                    {val > 0 && (
                      <text
                        x={LABEL_W + wi * (CELL_W + GAP) + CELL_W / 2}
                        y={20 + mi * (CELL_H + GAP) + CELL_H / 2 + 4}
                        textAnchor="middle"
                        fontSize={11}
                        fill="rgba(255,255,255,0.8)"
                      >
                        {val}
                      </text>
                    )}
                  </g>
                )
              })}
            </g>
          ))}
        </svg>
      </div>
    </div>
  )
}
