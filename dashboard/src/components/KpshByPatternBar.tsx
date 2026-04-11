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

export function KpshByPatternBar({ data }: Props) {
  const chartData = MOVEMENT_PATTERNS.map((p) => ({
    pattern: MOVEMENT_PATTERN_LABELS[p] ?? p,
    kpsh: data.kpsh_by_pattern[p] ?? 0,
  })).sort((a, b) => b.kpsh - a.kpsh)

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
      <h3 className="text-sm font-medium mb-3 text-neutral-200">КПШ по movement pattern</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 8, right: 16, left: 24, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
          <XAxis type="number" stroke="#737373" fontSize={11} />
          <YAxis type="category" dataKey="pattern" stroke="#737373" fontSize={11} width={70} />
          <Tooltip
            contentStyle={{
              background: '#171717',
              border: '1px solid #404040',
              borderRadius: 6,
              fontSize: 12,
            }}
          />
          <Bar dataKey="kpsh" fill="#34d399" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
