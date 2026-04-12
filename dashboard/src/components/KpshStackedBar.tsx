import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { BUCKETS, BUCKET_COLORS, BUCKET_LABELS } from '@/api/types'
import type { DashboardResponse } from '@/api/types'

interface Props {
  data: DashboardResponse
}

const tooltipStyle = {
  background: 'rgba(10, 10, 15, 0.95)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: 10,
  fontSize: 12,
  color: '#e5e5e5',
  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
}

export function KpshStackedBar({ data }: Props) {
  const chartData = data.days.map((d, i) => {
    const row: Record<string, string | number> = { day: d.slice(5) }
    for (const b of BUCKETS) row[b] = data.kpsh_by_bucket[b][i] ?? 0
    return row
  })

  return (
    <div className="glass-card">
      <h3 className="chart-title">КПШ по дням</h3>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="day" stroke="rgba(255,255,255,0.2)" fontSize={11} />
          <YAxis stroke="rgba(255,255,255,0.2)" fontSize={11} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {BUCKETS.map((b) => (
            <Bar
              key={b}
              dataKey={b}
              stackId="kpsh"
              name={BUCKET_LABELS[b]}
              fill={BUCKET_COLORS[b]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
