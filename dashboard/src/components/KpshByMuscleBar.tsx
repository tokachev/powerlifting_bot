import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { MUSCLE_GROUPS, MUSCLE_GROUP_LABELS } from '@/api/types'
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

export function KpshByMuscleBar({ data }: Props) {
  const chartData = MUSCLE_GROUPS.map((m) => ({
    muscle: MUSCLE_GROUP_LABELS[m] ?? m,
    kpsh: data.kpsh_by_muscle[m] ?? 0,
  })).sort((a, b) => b.kpsh - a.kpsh)

  return (
    <div className="glass-card">
      <h3 className="chart-title">КПШ по мышечным группам</h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 8, right: 16, left: 24, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis type="number" stroke="rgba(255,255,255,0.2)" fontSize={11} />
          <YAxis type="category" dataKey="muscle" stroke="rgba(255,255,255,0.2)" fontSize={11} width={70} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="kpsh" fill="#a78bfa" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
