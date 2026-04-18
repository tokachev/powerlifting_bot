import { useTranslation } from 'react-i18next'
import type { AccessoryItem } from '@/api/pl_types'
import { Card, EmptyState } from '../shared'

export function AccessoriesBars({ items }: { items: AccessoryItem[] }) {
  const { t } = useTranslation()
  if (items.length === 0) {
    return (
      <Card title={t('accessories')}>
        <EmptyState text={t('noData')} />
      </Card>
    )
  }
  const maxE = Math.max(...items.map((i) => i.e1rm_kg), 1)
  return (
    <Card title={t('accessories')} meta={`${items.length}`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {items.map((it) => {
          const pct = (it.e1rm_kg / maxE) * 100
          return (
            <div
              key={it.canonical_name}
              style={{
                display: 'grid',
                gridTemplateColumns: '1.2fr 3fr 1fr',
                gap: 8,
                fontSize: 12,
                alignItems: 'center',
              }}
            >
              <span className="muted" style={{ color: 'var(--fg-1)' }}>
                {it.canonical_name}
              </span>
              <div
                style={{
                  background: 'var(--bg-3)',
                  height: 14,
                  borderRadius: 3,
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    width: `${pct}%`,
                    height: '100%',
                    background: 'var(--accent)',
                    borderRadius: 3,
                  }}
                />
              </div>
              <span
                className="mono tabular"
                style={{
                  textAlign: 'right',
                  color: it.delta_kg >= 0 ? 'var(--good)' : 'var(--crit)',
                }}
              >
                {it.e1rm_kg.toFixed(1)}
                {it.delta_kg !== 0 && (
                  <span style={{ fontSize: 10, marginLeft: 4 }}>
                    {it.delta_kg >= 0 ? '+' : ''}
                    {it.delta_kg.toFixed(1)}
                  </span>
                )}
              </span>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
