import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { DashboardResponse } from '@/api/types'

interface Props {
  data: DashboardResponse
}

export function IntensityLine({ data }: Props) {
  const chartData = data.days.map((d, i) => ({
    day: d.slice(5),
    // Recharts skips Line at null values when connectNulls={false}
    intensity: data.intensity_kg[i],
  }))

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
      <h3 className="text-sm font-medium mb-3 text-neutral-200">Средняя интенсивность, кг</h3>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
          <XAxis dataKey="day" stroke="#737373" fontSize={11} />
          <YAxis stroke="#737373" fontSize={11} domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{
              background: '#171717',
              border: '1px solid #404040',
              borderRadius: 6,
              fontSize: 12,
            }}
            formatter={(v) => (v == null ? '—' : `${(v as number).toFixed(1)} кг`)}
          />
          <Line
            type="monotone"
            dataKey="intensity"
            stroke="#fbbf24"
            strokeWidth={2}
            connectNulls={false}
            dot={{ r: 3, fill: '#fbbf24' }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
