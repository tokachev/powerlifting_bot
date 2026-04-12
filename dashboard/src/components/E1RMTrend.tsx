import { useMemo } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { E1RMTrendResponse } from '@/api/types'
import { E1RM_EXERCISE_COLORS, E1RM_EXERCISE_LABELS } from '@/api/types'

interface Props {
  data: E1RMTrendResponse
}

const tooltipStyle = {
  background: 'rgba(10, 10, 15, 0.95)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: 10,
  fontSize: 12,
  color: '#e5e5e5',
  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
}

const DEFAULT_COLOR = '#a78bfa'

export function E1RMTrend({ data }: Props) {
  const { chartData, exercises } = useMemo(() => {
    // pivot: group points by date, one key per exercise
    const byDate = new Map<string, Record<string, number>>()
    const exerciseSet = new Set<string>()

    for (const p of data.points) {
      exerciseSet.add(p.canonical_name)
      let row = byDate.get(p.date)
      if (!row) {
        row = { date: p.date } as unknown as Record<string, number>
        byDate.set(p.date, row)
      }
      row[p.canonical_name] = p.estimated_1rm_kg
    }

    const sorted = Array.from(byDate.values()).sort((a, b) =>
      (a.date as unknown as string) < (b.date as unknown as string) ? -1 : 1,
    )
    return { chartData: sorted, exercises: Array.from(exerciseSet) }
  }, [data])

  if (chartData.length === 0) {
    return (
      <div className="glass-card">
        <h3 className="chart-title">e1RM тренд</h3>
        <div className="text-neutral-500 text-sm py-8 text-center">Нет данных</div>
      </div>
    )
  }

  return (
    <div className="glass-card">
      <h3 className="chart-title">e1RM тренд, кг</h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis
            dataKey="date"
            stroke="rgba(255,255,255,0.2)"
            fontSize={11}
            tickFormatter={(v: string) => v.slice(5)}
          />
          <YAxis stroke="rgba(255,255,255,0.2)" fontSize={11} domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={tooltipStyle}
            labelFormatter={(v: string) => v}
            formatter={(v: number, name: string) => [
              `${v.toFixed(1)} кг`,
              E1RM_EXERCISE_LABELS[name] ?? name,
            ]}
          />
          {exercises.map((ex) => {
            const color = E1RM_EXERCISE_COLORS[ex] ?? DEFAULT_COLOR
            return (
              <Line
                key={ex}
                type="monotone"
                dataKey={ex}
                stroke={color}
                strokeWidth={2.5}
                connectNulls
                dot={{ r: 3.5, fill: color, strokeWidth: 0 }}
                activeDot={{ r: 6, fill: color, stroke: `${color}40`, strokeWidth: 4 }}
              />
            )
          })}
        </LineChart>
      </ResponsiveContainer>
      <div className="flex gap-4 mt-2 justify-center text-xs text-neutral-400">
        {exercises.map((ex) => (
          <span key={ex} className="flex items-center gap-1.5">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ background: E1RM_EXERCISE_COLORS[ex] ?? DEFAULT_COLOR }}
            />
            {E1RM_EXERCISE_LABELS[ex] ?? ex}
          </span>
        ))}
      </div>
    </div>
  )
}
