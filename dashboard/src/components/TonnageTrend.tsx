import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { TonnageTrendResponse } from '@/api/types'

interface Props {
  data: TonnageTrendResponse
}

const tooltipStyle = {
  background: 'rgba(10, 10, 15, 0.95)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: 10,
  fontSize: 12,
  color: '#e5e5e5',
  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
}

export function TonnageTrend({ data }: Props) {
  const chartData = data.weeks.map((w) => ({
    week: w.iso_week,
    tonnage: Math.round(w.tonnage_kg),
  }))

  if (chartData.length === 0) {
    return (
      <div className="glass-card">
        <h3 className="chart-title">Тоннаж / неделя</h3>
        <div className="text-neutral-500 text-sm py-8 text-center">Нет данных</div>
      </div>
    )
  }

  return (
    <div className="glass-card">
      <h3 className="chart-title">Тоннаж / неделя, кг</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis
            dataKey="week"
            stroke="rgba(255,255,255,0.2)"
            fontSize={11}
            tickFormatter={(v: string) => v.slice(5)}
          />
          <YAxis stroke="rgba(255,255,255,0.2)" fontSize={11} />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v: number) => [`${v.toLocaleString()} кг`, 'Тоннаж']}
          />
          <Bar dataKey="tonnage" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
