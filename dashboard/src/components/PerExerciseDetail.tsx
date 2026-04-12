import { useMemo } from 'react'
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { PerExerciseResponse } from '@/api/types'

interface Props {
  data: PerExerciseResponse
  exerciseName: string
}

const tooltipStyle = {
  background: 'rgba(10, 10, 15, 0.95)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: 10,
  fontSize: 12,
  color: '#e5e5e5',
  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
}

export function PerExerciseDetail({ data, exerciseName }: Props) {
  const chartData = useMemo(() => {
    return data.sessions.map((s) => ({
      date: s.date,
      e1rm: s.best_e1rm_kg > 0 ? s.best_e1rm_kg : null,
      volume: s.total_volume_kg,
      sets: s.sets.length,
    }))
  }, [data])

  if (chartData.length === 0) {
    return (
      <div className="glass-card">
        <h3 className="chart-title">{exerciseName}: нет данных</h3>
      </div>
    )
  }

  return (
    <div className="glass-card">
      <h3 className="chart-title">{exerciseName}: e1RM и тоннаж</h3>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis
            dataKey="date"
            stroke="rgba(255,255,255,0.2)"
            fontSize={11}
            tickFormatter={(v: string) => v.slice(5)}
          />
          <YAxis yAxisId="left" stroke="rgba(255,255,255,0.2)" fontSize={11} />
          <YAxis yAxisId="right" orientation="right" stroke="rgba(255,255,255,0.2)" fontSize={11} />
          <Tooltip contentStyle={tooltipStyle} />
          <Scatter yAxisId="left" dataKey="volume" fill="#3b82f680" name="Тоннаж, кг" />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="e1rm"
            stroke="#f97316"
            strokeWidth={2.5}
            connectNulls
            dot={{ r: 3.5, fill: '#f97316', strokeWidth: 0 }}
            name="e1RM, кг"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
