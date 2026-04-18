import { useTranslation } from 'react-i18next'
import type { RepMaxEntry } from '@/api/pl_types'
import { Card } from '../shared'

export function RepMaxTable({ entries }: { entries: RepMaxEntry[] }) {
  const { t } = useTranslation()
  return (
    <Card title={t('repMax')}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, 1fr)',
          gap: 8,
        }}
      >
        {entries.map((e) => (
          <div
            key={e.reps}
            style={{
              background: 'var(--bg-2)',
              border: '1px solid var(--line)',
              borderRadius: 'var(--r)',
              padding: 10,
              textAlign: 'center',
            }}
          >
            <div
              className="mono"
              style={{
                fontSize: 10,
                color: 'var(--fg-3)',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
              }}
            >
              {e.reps}RM
            </div>
            <div
              className="mono tabular"
              style={{ fontSize: 20, fontWeight: 700, color: 'var(--fg)', marginTop: 4 }}
            >
              {e.weight_kg.toFixed(1)}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
