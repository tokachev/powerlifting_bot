import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { MeetEntry } from '@/api/pl_types'
import { Card, EmptyState } from '../shared'

type Mode = 'wilks' | 'dots' | 'ipf_gl'

export function WilksDotsChart({ meets }: { meets: MeetEntry[] }) {
  const { t } = useTranslation()
  const [mode, setMode] = useState<Mode>('wilks')
  if (meets.length === 0) {
    return (
      <Card title={`${t('wilks')} / ${t('dots')}`}>
        <EmptyState text={t('noMeets')} />
      </Card>
    )
  }
  const data = meets.map((m) => ({
    date: m.date,
    v: (m[mode] as number | null) ?? 0,
  }))
  const label = mode === 'wilks' ? t('wilks') : mode === 'dots' ? t('dots') : 'IPF GL'
  return (
    <Card
      title={label}
      meta={
        <div className="seg">
          {(['wilks', 'dots', 'ipf_gl'] as Mode[]).map((m) => (
            <button key={m} className={m === mode ? 'on' : ''} onClick={() => setMode(m)}>
              {m.toUpperCase().replace('_', '·')}
            </button>
          ))}
        </div>
      }
    >
      <div style={{ height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, left: -8, bottom: 4 }}>
            <defs>
              <linearGradient id="wd-g" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.6} />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--line)" strokeDasharray="2 2" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: 'var(--fg-3)', fontSize: 10, fontFamily: 'var(--f-mono)' }}
              axisLine={{ stroke: 'var(--line)' }}
            />
            <YAxis
              tick={{ fill: 'var(--fg-3)', fontSize: 10, fontFamily: 'var(--f-mono)' }}
              axisLine={{ stroke: 'var(--line)' }}
              domain={['dataMin - 5', 'dataMax + 5']}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-3)',
                border: '1px solid var(--line-2)',
                fontFamily: 'var(--f-mono)',
                fontSize: 11,
              }}
            />
            <Area type="monotone" dataKey="v" stroke="var(--accent)" strokeWidth={2} fill="url(#wd-g)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
