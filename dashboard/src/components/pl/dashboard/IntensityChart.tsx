import { useTranslation } from 'react-i18next'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Lift, LiftWeekPoint } from '@/api/pl_types'
import { Card } from '../shared'

export function IntensityChart({ data }: { data: Record<Lift, LiftWeekPoint[]> }) {
  const { t } = useTranslation()
  const weeks = Array.from(
    new Set([...data.squat, ...data.bench, ...data.deadlift].map((p) => p.iso_week)),
  ).sort()
  const merged = weeks.map((w) => ({
    iso_week: w,
    squat: data.squat.find((p) => p.iso_week === w)?.intensity_pct ?? null,
    bench: data.bench.find((p) => p.iso_week === w)?.intensity_pct ?? null,
    deadlift: data.deadlift.find((p) => p.iso_week === w)?.intensity_pct ?? null,
  }))
  return (
    <Card title={t('intensity')}>
      <div style={{ height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={merged} margin={{ top: 4, right: 4, left: -8, bottom: 4 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="2 2" vertical={false} />
            <XAxis
              dataKey="iso_week"
              tick={{ fill: 'var(--fg-3)', fontSize: 10, fontFamily: 'var(--f-mono)' }}
              axisLine={{ stroke: 'var(--line)' }}
              tickFormatter={(v: string) => v.split('-W')[1] ?? v}
            />
            <YAxis
              tick={{ fill: 'var(--fg-3)', fontSize: 10, fontFamily: 'var(--f-mono)' }}
              axisLine={{ stroke: 'var(--line)' }}
              domain={['dataMin - 5', 'dataMax + 5']}
              unit="%"
            />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-3)',
                border: '1px solid var(--line-2)',
                fontFamily: 'var(--f-mono)',
                fontSize: 11,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'var(--f-mono)' }} />
            <Line
              type="monotone"
              dataKey="squat"
              stroke="var(--squat)"
              dot={false}
              strokeWidth={2}
              connectNulls
              name={t('squat')}
            />
            <Line
              type="monotone"
              dataKey="bench"
              stroke="var(--bench)"
              dot={false}
              strokeWidth={2}
              connectNulls
              name={t('bench')}
            />
            <Line
              type="monotone"
              dataKey="deadlift"
              stroke="var(--dead)"
              dot={false}
              strokeWidth={2}
              connectNulls
              name={t('deadlift')}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
