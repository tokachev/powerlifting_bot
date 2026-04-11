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

export function KpshStackedBar({ data }: Props) {
  const chartData = data.days.map((d, i) => {
    const row: Record<string, string | number> = { day: d.slice(5) }
    for (const b of BUCKETS) row[b] = data.kpsh_by_bucket[b][i] ?? 0
    return row
  })

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
      <h3 className="text-sm font-medium mb-3 text-neutral-200">КПШ по дням</h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
          <XAxis dataKey="day" stroke="#737373" fontSize={11} />
          <YAxis stroke="#737373" fontSize={11} />
          <Tooltip
            contentStyle={{
              background: '#171717',
              border: '1px solid #404040',
              borderRadius: 6,
              fontSize: 12,
            }}
          />
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
