import { useTranslation } from 'react-i18next'
import { Area, AreaChart, ResponsiveContainer } from 'recharts'
import type { ReadinessSummary } from '@/api/pl_types'
import { Card, EmptyState } from '../shared'

export function ReadinessWidget({ data }: { data: ReadinessSummary }) {
  const { t } = useTranslation()
  if (!data.points || data.points.length === 0) {
    return (
      <Card title={t('readiness')}>
        <EmptyState text={t('noRecovery')} />
      </Card>
    )
  }
  const rec = data.latest_recovery_pct ?? 0
  const sleep = data.points.map((p, i) => ({ x: i, y: p.sleep_hours ?? 0 }))
  return (
    <Card title={t('readiness')} meta="28d">
      <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 16, alignItems: 'center' }}>
        <RadialGauge value={rec} />
        <div>
          <table className="tbl" style={{ fontSize: 11 }}>
            <tbody>
              <tr>
                <td className="muted">{t('sleep')}</td>
                <td className="num">{data.avg_sleep_hours?.toFixed(1) ?? '—'} h</td>
              </tr>
              <tr>
                <td className="muted">HRV</td>
                <td className="num">{data.avg_hrv_ms?.toFixed(0) ?? '—'} ms</td>
              </tr>
              <tr>
                <td className="muted">RHR</td>
                <td className="num">{data.avg_rhr_bpm?.toFixed(0) ?? '—'} bpm</td>
              </tr>
            </tbody>
          </table>
          <div style={{ height: 50, marginTop: 8 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sleep}>
                <defs>
                  <linearGradient id="sl-g" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="y"
                  stroke="var(--accent)"
                  fill="url(#sl-g)"
                  strokeWidth={2}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </Card>
  )
}

function RadialGauge({ value }: { value: number }) {
  const r = 46
  const C = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, value))
  const offset = C * (1 - pct / 100)
  const color =
    pct >= 70 ? 'var(--good)' : pct >= 40 ? 'var(--warn)' : 'var(--crit)'
  return (
    <svg viewBox="0 0 120 120" width={120} height={120}>
      <circle cx="60" cy="60" r={r} stroke="var(--bg-3)" strokeWidth="10" fill="none" />
      <circle
        cx="60"
        cy="60"
        r={r}
        stroke={color}
        strokeWidth="10"
        fill="none"
        strokeLinecap="round"
        strokeDasharray={C}
        strokeDashoffset={offset}
        transform="rotate(-90 60 60)"
      />
      <text
        x="60"
        y="65"
        textAnchor="middle"
        fill="var(--fg)"
        fontSize="22"
        fontFamily="var(--f-disp)"
        fontWeight="700"
      >
        {pct}%
      </text>
    </svg>
  )
}
