import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { MOVEMENT_PATTERNS, MOVEMENT_PATTERN_LABELS } from '@/api/types'
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

export function KpshByPatternBar({ data }: Props) {
  const chartData = MOVEMENT_PATTERNS.map((p) => ({
    pattern: MOVEMENT_PATTERN_LABELS[p] ?? p,
    kpsh: data.kpsh_by_pattern[p] ?? 0,
  })).sort((a, b) => b.kpsh - a.kpsh)

  return (
    <div className="glass-card">
      <h3 className="chart-title">КПШ по movement pattern</h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 8, right: 16, left: 24, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis type="number" stroke="rgba(255,255,255,0.2)" fontSize={11} />
          <YAxis type="category" dataKey="pattern" stroke="rgba(255,255,255,0.2)" fontSize={11} width={70} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="kpsh" fill="#34d399" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
