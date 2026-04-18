import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Lift, LiftWeekPoint } from '@/api/pl_types'
import { Card } from '../shared'

function accentFor(lift: Lift) {
  return lift === 'squat' ? 'var(--squat)' : lift === 'bench' ? 'var(--bench)' : 'var(--dead)'
}

export function E1RMProgressionChart({
  weekly,
  target,
  lift,
}: {
  weekly: LiftWeekPoint[]
  target: number
  lift: Lift
}) {
  const { t } = useTranslation()
  const data = weekly.map((w) => ({ x: w.iso_week, e1rm: w.e1rm_kg }))
  const accent = accentFor(lift)
  return (
    <Card title={`${t('e1rm')} · ${weekly.length} ${t('weekShort')}`}>
      <div style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, left: -8, bottom: 4 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="2 2" vertical={false} />
            <XAxis
              dataKey="x"
              tick={{ fill: 'var(--fg-3)', fontSize: 10, fontFamily: 'var(--f-mono)' }}
              tickFormatter={(v: string) => v.split('-W')[1] ?? v}
              axisLine={{ stroke: 'var(--line)' }}
            />
            <YAxis
              tick={{ fill: 'var(--fg-3)', fontSize: 10, fontFamily: 'var(--f-mono)' }}
              axisLine={{ stroke: 'var(--line)' }}
              domain={['dataMin - 10', 'dataMax + 10']}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-3)',
                border: '1px solid var(--line-2)',
                fontFamily: 'var(--f-mono)',
                fontSize: 11,
              }}
            />
            {target > 0 && <ReferenceLine y={target} stroke="var(--accent)" strokeDasharray="4 2" />}
            <Line
              type="monotone"
              dataKey="e1rm"
              stroke={accent}
              strokeWidth={2}
              dot={{ r: 2.5, fill: accent }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

export function LiftTonnageChart({ weekly, lift }: { weekly: LiftWeekPoint[]; lift: Lift }) {
  const { t } = useTranslation()
  const data = weekly.map((w) => ({ x: w.iso_week, v: w.tonnage_kg }))
  const accent = accentFor(lift)
  return (
    <Card title={t('weeklyTonnage')} meta={`${t('kg')}`}>
      <div style={{ height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, left: -8, bottom: 4 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="2 2" vertical={false} />
            <XAxis
              dataKey="x"
              tick={{ fill: 'var(--fg-3)', fontSize: 10 }}
              tickFormatter={(v: string) => v.split('-W')[1] ?? v}
              axisLine={{ stroke: 'var(--line)' }}
            />
            <YAxis tick={{ fill: 'var(--fg-3)', fontSize: 10 }} axisLine={{ stroke: 'var(--line)' }} />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-3)',
                border: '1px solid var(--line-2)',
                fontFamily: 'var(--f-mono)',
                fontSize: 11,
              }}
            />
            <Bar dataKey="v" fill={accent} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

export function LiftIntensityChart({ weekly, lift }: { weekly: LiftWeekPoint[]; lift: Lift }) {
  const { t } = useTranslation()
  const data = weekly.map((w) => ({ x: w.iso_week, v: w.intensity_pct }))
  const accent = accentFor(lift)
  return (
    <Card title={t('intensity')}>
      <div style={{ height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, left: -8, bottom: 4 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="2 2" vertical={false} />
            <XAxis
              dataKey="x"
              tick={{ fill: 'var(--fg-3)', fontSize: 10 }}
              tickFormatter={(v: string) => v.split('-W')[1] ?? v}
              axisLine={{ stroke: 'var(--line)' }}
            />
            <YAxis
              tick={{ fill: 'var(--fg-3)', fontSize: 10 }}
              axisLine={{ stroke: 'var(--line)' }}
              unit="%"
              domain={[50, 100]}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-3)',
                border: '1px solid var(--line-2)',
                fontFamily: 'var(--f-mono)',
                fontSize: 11,
              }}
            />
            <Line type="monotone" dataKey="v" stroke={accent} strokeWidth={2} connectNulls dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

export function BarVelocityChart({ weekly, lift }: { weekly: LiftWeekPoint[]; lift: Lift }) {
  const { t } = useTranslation()
  const data = weekly.map((w) => ({ x: w.iso_week, v: w.avg_velocity_ms }))
  const hasData = data.some((d) => d.v !== null && d.v !== undefined)
  const accent = accentFor(lift)
  return (
    <Card title={t('velocity')} meta="m/s">
      <div style={{ height: 180 }}>
        {hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 4, left: -8, bottom: 4 }}>
              <CartesianGrid stroke="var(--line)" strokeDasharray="2 2" vertical={false} />
              <XAxis
                dataKey="x"
                tick={{ fill: 'var(--fg-3)', fontSize: 10 }}
                tickFormatter={(v: string) => v.split('-W')[1] ?? v}
                axisLine={{ stroke: 'var(--line)' }}
              />
              <YAxis
                tick={{ fill: 'var(--fg-3)', fontSize: 10 }}
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
              <Line type="monotone" dataKey="v" stroke={accent} strokeWidth={2} connectNulls dot={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="mono" style={{ color: 'var(--fg-3)', padding: 16 }}>
            {t('noData')}
          </div>
        )}
      </div>
    </Card>
  )
}
