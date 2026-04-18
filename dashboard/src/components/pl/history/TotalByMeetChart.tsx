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
import type { MeetEntry } from '@/api/pl_types'
import { Card, EmptyState } from '../shared'

export function TotalByMeetChart({ meets }: { meets: MeetEntry[] }) {
  const { t } = useTranslation()
  if (meets.length === 0) {
    return (
      <Card title={t('meetHistory')}>
        <EmptyState text={t('noMeets')} />
      </Card>
    )
  }
  const data = meets.map((m) => ({
    date: m.date,
    total: m.total_kg,
    squat: m.squat_kg,
    bench: m.bench_kg,
    deadlift: m.deadlift_kg,
  }))
  return (
    <Card title={t('meetHistory')} meta={`${meets.length}`}>
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, left: -8, bottom: 4 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="2 2" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: 'var(--fg-3)', fontSize: 10, fontFamily: 'var(--f-mono)' }}
              axisLine={{ stroke: 'var(--line)' }}
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
            <Line type="monotone" dataKey="total" stroke="var(--fg)" strokeWidth={2.5} dot={{ r: 3 }} name={t('total')} />
            <Line type="monotone" dataKey="squat" stroke="var(--squat)" strokeWidth={2} dot={{ r: 2 }} name={t('squat')} />
            <Line type="monotone" dataKey="bench" stroke="var(--bench)" strokeWidth={2} dot={{ r: 2 }} name={t('bench')} />
            <Line type="monotone" dataKey="deadlift" stroke="var(--dead)" strokeWidth={2} dot={{ r: 2 }} name={t('deadlift')} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
