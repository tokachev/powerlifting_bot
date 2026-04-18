import { useTranslation } from 'react-i18next'
import type { TechniqueNoteItem } from '@/api/pl_types'
import { Card, EmptyState } from '../shared'

export function TechniqueNotes({ items }: { items: TechniqueNoteItem[] }) {
  const { t } = useTranslation()
  if (items.length === 0) {
    return (
      <Card title={t('techniqueNotes')}>
        <EmptyState text={t('noTechniqueNotes')} />
      </Card>
    )
  }
  return (
    <Card title={t('techniqueNotes')} meta={`${items.length}`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map((n) => (
          <div
            key={n.id}
            style={{
              padding: '8px 10px',
              background: 'var(--bg-2)',
              border: '1px solid var(--line)',
              borderRadius: 'var(--r)',
              fontSize: 12,
            }}
          >
            <div
              className="mono"
              style={{
                fontSize: 10,
                color: 'var(--fg-3)',
                marginBottom: 4,
                display: 'flex',
                justifyContent: 'space-between',
              }}
            >
              <span>{n.recorded_date}</span>
              <span style={{ textTransform: 'uppercase' }}>{n.source}</span>
            </div>
            <div>{n.note_text}</div>
          </div>
        ))}
      </div>
    </Card>
  )
}
