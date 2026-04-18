import { useTranslation } from 'react-i18next'
import type { SetRecommendationItem } from '@/api/pl_types'
import { Card } from '../shared'

export function SetRecommendations({ items }: { items: SetRecommendationItem[] }) {
  const { t } = useTranslation()
  return (
    <Card title={t('setRecommendation')}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {items.map((r) => (
          <div
            key={r.name}
            style={{
              background: 'var(--bg-2)',
              border: '1px solid var(--line)',
              borderRadius: 'var(--r)',
              padding: 12,
            }}
          >
            <div
              className="mono upper"
              style={{ color: 'var(--fg-3)', fontSize: 10, letterSpacing: '0.12em' }}
            >
              {r.name}
            </div>
            <div
              className="mono tabular"
              style={{ fontSize: 26, color: 'var(--fg)', fontWeight: 700, marginTop: 6 }}
            >
              {r.weight_kg.toFixed(1)}
            </div>
            <div
              className="mono"
              style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 4 }}
            >
              {r.scheme} @ {r.intensity_pct}%
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
