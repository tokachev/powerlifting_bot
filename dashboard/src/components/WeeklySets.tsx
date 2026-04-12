import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { WeeklySetsResponse } from '@/api/types'
import { MUSCLE_GROUP_COLORS, MUSCLE_GROUP_LABELS, MUSCLE_GROUPS } from '@/api/types'

interface Props {
  data: WeeklySetsResponse
}

const tooltipStyle = {
  background: 'rgba(10, 10, 15, 0.95)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: 10,
  fontSize: 12,
  color: '#e5e5e5',
  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
}

export function WeeklySets({ data }: Props) {
  const { chartData, muscles } = useMemo(() => {
    // pivot: one row per week, columns = muscle groups
    const byWeek = new Map<string, Record<string, number>>()
    const muscleSet = new Set<string>()

    for (const b of data.buckets) {
      muscleSet.add(b.muscle_group)
      let row = byWeek.get(b.iso_week)
      if (!row) {
        row = { week: b.iso_week }
        byWeek.set(b.iso_week, row)
      }
      row[b.muscle_group] = (row[b.muscle_group] ?? 0) + b.hard_sets
    }

    const sorted = Array.from(byWeek.values()).sort((a, b) =>
      (a.week as string) < (b.week as string) ? -1 : 1,
    )
    // maintain consistent order
    const muscles = MUSCLE_GROUPS.filter((m) => muscleSet.has(m))
    return { chartData: sorted, muscles }
  }, [data])

  if (chartData.length === 0) {
    return (
      <div className="glass-card">
        <h3 className="chart-title">Hard-сеты по мышцам / неделя</h3>
        <div className="text-neutral-500 text-sm py-8 text-center">Нет данных</div>
      </div>
    )
  }

  return (
    <div className="glass-card">
      <h3 className="chart-title">Hard-сеты по мышцам / неделя</h3>
      <ResponsiveContainer width="100%" height={280}>
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
            formatter={(v: number, name: string) => [
              `${v} сетов`,
              MUSCLE_GROUP_LABELS[name] ?? name,
            ]}
          />
          {muscles.map((m) => (
            <Bar
              key={m}
              dataKey={m}
              stackId="sets"
              fill={MUSCLE_GROUP_COLORS[m] ?? '#6b7280'}
              name={m}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <div className="flex gap-4 mt-2 justify-center flex-wrap text-xs text-neutral-400">
        {muscles.map((m) => (
          <span key={m} className="flex items-center gap-1.5">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ background: MUSCLE_GROUP_COLORS[m] ?? '#6b7280' }}
            />
            {MUSCLE_GROUP_LABELS[m] ?? m}
          </span>
        ))}
      </div>
    </div>
  )
}
