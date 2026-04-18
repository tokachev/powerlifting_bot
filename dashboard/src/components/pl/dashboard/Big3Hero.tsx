import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Area, AreaChart, ResponsiveContainer } from 'recharts'
import type { Big3LiftCard, Lift, LiftWeekPoint } from '@/api/pl_types'
import { LiftDot, Meter } from '../shared'

export function Big3Hero({
  big3,
  byLift,
}: {
  big3: Big3LiftCard[]
  byLift: Record<Lift, LiftWeekPoint[]>
}) {
  const { t } = useTranslation()
  return (
    <div className="big3">
      {big3.map((card) => {
        const series = byLift[card.lift] ?? []
        const data = series.map((p) => ({ x: p.iso_week, y: p.e1rm_kg }))
        const color =
          card.lift === 'squat'
            ? 'var(--squat)'
            : card.lift === 'bench'
              ? 'var(--bench)'
              : 'var(--dead)'
        const tgtPct = card.target_kg > 0
          ? Math.round((card.current_e1rm_kg / card.target_kg) * 100)
          : 0
        return (
          <Link
            to={`/lifts/${card.lift}`}
            key={card.lift}
            className="lift-card"
            style={{ textDecoration: 'none' }}
          >
            <div className="hd">
              <span className="lift-name">
                <LiftDot lift={card.lift} /> {t(card.lift)}
              </span>
              <span className="lift-color" style={{ background: color }} />
            </div>
            <div className="big-val mono">
              {card.current_e1rm_kg.toFixed(1)}
              <span className="unit">{t('kg')}</span>
            </div>
            <div className="delta-row">
              <span className={`delta${card.delta_pct < 0 ? ' neg' : ''}`}>
                {card.delta_pct >= 0 ? '+' : ''}
                {card.delta_pct}% {t('vsPrev')}
              </span>
              <span>
                {t('pr')}: <b>{card.pr_kg.toFixed(1)}</b>
              </span>
              {card.target_kg > 0 && (
                <span>
                  {t('target')}: <b>{card.target_kg.toFixed(1)}</b>
                </span>
              )}
            </div>
            {card.target_kg > 0 && <Meter value={tgtPct} max={100} />}
            {data.length > 1 && (
              <div className="sparkline" style={{ height: 50 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data}>
                    <defs>
                      <linearGradient id={`gr-${card.lift}`} x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity={0.6} />
                        <stop offset="100%" stopColor={color} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area
                      type="monotone"
                      dataKey="y"
                      stroke={color}
                      strokeWidth={2}
                      fill={`url(#gr-${card.lift})`}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </Link>
        )
      })}
    </div>
  )
}
