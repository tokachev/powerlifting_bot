import { useTranslation } from 'react-i18next'
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
import type { Lift, LiftWeekPoint } from '@/api/pl_types'
import { Card } from '../shared'

export function TonnageByLift({
  data,
  phases,
}: {
  data: Record<Lift, LiftWeekPoint[]>
  phases: string[]
}) {
  const { t } = useTranslation()
  // merge: [{iso_week, squat, bench, deadlift}]
  const weeks = Array.from(
    new Set(
      [...data.squat, ...data.bench, ...data.deadlift].map((p) => p.iso_week),
    ),
  ).sort()
  const merged = weeks.map((w) => ({
    iso_week: w,
    squat: data.squat.find((p) => p.iso_week === w)?.tonnage_kg ?? 0,
    bench: data.bench.find((p) => p.iso_week === w)?.tonnage_kg ?? 0,
    deadlift: data.deadlift.find((p) => p.iso_week === w)?.tonnage_kg ?? 0,
  }))
  return (
    <Card title={t('tonnageByLift')} meta={`${weeks.length} ${t('weekShort')}`}>
      <div style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={merged} margin={{ top: 4, right: 4, left: -8, bottom: 4 }}>
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
            <Bar dataKey="squat" stackId="t" fill="var(--squat)" name={t('squat')} />
            <Bar dataKey="bench" stackId="t" fill="var(--bench)" name={t('bench')} />
            <Bar dataKey="deadlift" stackId="t" fill="var(--dead)" name={t('deadlift')} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {phases.length > 0 && (
        <div className="phases-strip" style={{ marginTop: 8 }}>
          {phases.map((ph, i) => {
            const col =
              ph === 'hypertrophy'
                ? 'var(--dead)'
                : ph === 'strength'
                  ? 'var(--accent)'
                  : ph === 'peaking'
                    ? 'var(--bench)'
                    : ph === 'deload'
                      ? 'var(--fg-3)'
                      : 'var(--line-2)'
            return <span key={i} style={{ flex: 1, background: col }} />
          })}
        </div>
      )}
    </Card>
  )
}
