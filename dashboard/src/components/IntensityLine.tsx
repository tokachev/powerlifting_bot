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

const tooltipStyle = {
  background: 'rgba(10, 10, 15, 0.95)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: 10,
  fontSize: 12,
  color: '#e5e5e5',
  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
}

export function IntensityLine({ data }: Props) {
  const chartData = data.days.map((d, i) => ({
    day: d.slice(5),
    // Recharts skips Line at null values when connectNulls={false}
    intensity: data.intensity_kg[i],
  }))

  return (
    <div className="glass-card">
      <h3 className="chart-title">Средняя интенсивность, кг</h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="day" stroke="rgba(255,255,255,0.2)" fontSize={11} />
          <YAxis stroke="rgba(255,255,255,0.2)" fontSize={11} domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v) => (v == null ? '—' : `${(v as number).toFixed(1)} кг`)}
          />
          <Line
            type="monotone"
            dataKey="intensity"
            stroke="#fbbf24"
            strokeWidth={2.5}
            connectNulls={false}
            dot={{ r: 3.5, fill: '#fbbf24', strokeWidth: 0 }}
            activeDot={{ r: 6, fill: '#fbbf24', stroke: '#fbbf2440', strokeWidth: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
