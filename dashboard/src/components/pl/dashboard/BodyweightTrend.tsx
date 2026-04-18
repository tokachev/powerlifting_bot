import { useTranslation } from 'react-i18next'
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { BodyweightPoint } from '@/api/pl_types'
import { Card, EmptyState } from '../shared'

export function BodyweightTrend({ points }: { points: BodyweightPoint[] }) {
  const { t } = useTranslation()
  if (points.length === 0) {
    return (
      <Card title={t('bodyweightTrend')}>
        <EmptyState text={t('noData')} />
      </Card>
    )
  }
  return (
    <Card title={t('bodyweightTrend')} meta={`${points.length}`}>
      <div style={{ height: 130 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 4, right: 4, left: -8, bottom: 4 }}>
            <defs>
              <linearGradient id="bw-g" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.5} />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" tick={{ fill: 'var(--fg-3)', fontSize: 9 }} hide />
            <YAxis
              tick={{ fill: 'var(--fg-3)', fontSize: 10, fontFamily: 'var(--f-mono)' }}
              domain={['dataMin - 1', 'dataMax + 1']}
              axisLine={{ stroke: 'var(--line)' }}
              unit={` ${t('kg')}`}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-3)',
                border: '1px solid var(--line-2)',
                fontFamily: 'var(--f-mono)',
                fontSize: 11,
              }}
            />
            <Area
              type="monotone"
              dataKey="weight_kg"
              stroke="var(--accent)"
              strokeWidth={2}
              fill="url(#bw-g)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
