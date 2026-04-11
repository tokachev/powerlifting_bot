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

export function KpshByMuscleBar({ data }: Props) {
  const chartData = MUSCLE_GROUPS.map((m) => ({
    muscle: MUSCLE_GROUP_LABELS[m] ?? m,
    kpsh: data.kpsh_by_muscle[m] ?? 0,
  })).sort((a, b) => b.kpsh - a.kpsh)

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
      <h3 className="text-sm font-medium mb-3 text-neutral-200">КПШ по мышечным группам</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 8, right: 16, left: 24, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
          <XAxis type="number" stroke="#737373" fontSize={11} />
          <YAxis type="category" dataKey="muscle" stroke="#737373" fontSize={11} width={70} />
          <Tooltip
            contentStyle={{
              background: '#171717',
              border: '1px solid #404040',
              borderRadius: 6,
              fontSize: 12,
            }}
          />
          <Bar dataKey="kpsh" fill="#a78bfa" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
