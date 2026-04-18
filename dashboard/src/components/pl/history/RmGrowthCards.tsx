import { useTranslation } from 'react-i18next'
import type { RmGrowthItem } from '@/api/pl_types'
import { Card, LiftDot } from '../shared'

export function RmGrowthCards({ items }: { items: RmGrowthItem[] }) {
  const { t } = useTranslation()
  return (
    <Card title={t('rmGrowth')}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {items.map((g) => {
          const color =
            g.lift === 'squat'
              ? 'var(--squat)'
              : g.lift === 'bench'
                ? 'var(--bench)'
                : 'var(--dead)'
          return (
            <div
              key={g.lift}
              style={{
                background: 'var(--bg-2)',
                border: '1px solid var(--line)',
                borderRadius: 'var(--r)',
                padding: 14,
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <div
                style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: color }}
              />
              <div
                className="mono upper"
                style={{ color: 'var(--fg-3)', fontSize: 10, letterSpacing: '0.12em', marginTop: 2 }}
              >
                <LiftDot lift={g.lift} /> {t(g.lift)}
              </div>
              <div
                className="mono tabular"
                style={{ fontSize: 22, fontWeight: 700, color: 'var(--fg)', marginTop: 6 }}
              >
                {g.start_kg.toFixed(1)} → {g.end_kg.toFixed(1)}
              </div>
              <div
                className="mono"
                style={{
                  fontSize: 12,
                  marginTop: 4,
                  color: g.delta_kg >= 0 ? 'var(--good)' : 'var(--crit)',
                }}
              >
                {g.delta_kg >= 0 ? '+' : ''}
                {g.delta_kg.toFixed(1)} {t('kg')} ({g.delta_pct >= 0 ? '+' : ''}
                {g.delta_pct}%)
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
