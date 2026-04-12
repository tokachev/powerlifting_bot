import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { RepDistributionResponse } from '@/api/types'

interface Props {
  data: RepDistributionResponse
}

const tooltipStyle = {
  background: 'rgba(10, 10, 15, 0.95)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: 10,
  fontSize: 12,
  color: '#e5e5e5',
  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
}

export function RepDistribution({ data }: Props) {
  const chartData = data.buckets.map((b) => ({
    range: b.rep_range,
    sets: b.set_count,
    reps: b.rep_count,
  }))

  const hasData = chartData.some((d) => d.sets > 0)
  if (!hasData) {
    return (
      <div className="glass-card">
        <h3 className="chart-title">Распределение повторений</h3>
        <div className="text-neutral-500 text-sm py-8 text-center">Нет данных</div>
      </div>
    )
  }

  return (
    <div className="glass-card">
      <h3 className="chart-title">Распределение повторений</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="range" stroke="rgba(255,255,255,0.2)" fontSize={11} />
          <YAxis stroke="rgba(255,255,255,0.2)" fontSize={11} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="sets" fill="#3b82f6" name="Сеты" radius={[4, 4, 0, 0]} />
          <Bar dataKey="reps" fill="#22c55e" name="Повторения" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
