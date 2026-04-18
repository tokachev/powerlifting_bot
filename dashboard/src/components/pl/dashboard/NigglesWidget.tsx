import { useTranslation } from 'react-i18next'
import type { NiggleItem } from '@/api/pl_types'
import { Card, Chip, EmptyState } from '../shared'

export function NigglesWidget({ items }: { items: NiggleItem[] }) {
  const { t } = useTranslation()
  if (items.length === 0) {
    return (
      <Card title={t('niggles')}>
        <EmptyState text={t('noNiggles')} />
      </Card>
    )
  }
  return (
    <Card title={t('niggles')} meta={`${items.length}`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map((n) => (
          <div
            key={n.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr auto auto',
              gap: 10,
              alignItems: 'center',
              fontSize: 12,
              padding: '6px 0',
              borderBottom: '1px solid var(--line)',
            }}
          >
            <div>
              <div>{n.body_area}</div>
              {n.note && (
                <div style={{ color: 'var(--fg-3)', fontSize: 11 }}>{n.note}</div>
              )}
            </div>
            <Chip kind={n.severity}>{t(n.severity === 'good' ? 'good' : n.severity === 'warn' ? 'warning' : 'critical')}</Chip>
            <span className="mono" style={{ color: 'var(--fg-3)', fontSize: 10 }}>
              {n.recorded_date}
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}
