import { useTranslation } from 'react-i18next'
import type { PersonalRecordCard as PR } from '@/api/pl_types'
import { Card, LiftDot } from '../shared'

export function PersonalRecordsCards({ items }: { items: PR[] }) {
  const { t } = useTranslation()
  return (
    <Card title={t('personalRecords')}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {items.map((p) => {
          const color =
            p.lift === 'squat'
              ? 'var(--squat)'
              : p.lift === 'bench'
                ? 'var(--bench)'
                : 'var(--dead)'
          return (
            <div
              key={p.lift}
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
                <LiftDot lift={p.lift} /> {t(p.lift)}
              </div>
              <div
                className="mono tabular"
                style={{ fontSize: 30, fontWeight: 700, color: 'var(--fg)', marginTop: 6 }}
              >
                {p.weight_kg.toFixed(1)}
                <span style={{ fontSize: 12, color: 'var(--fg-2)', marginLeft: 4 }}>{t('kg')}</span>
              </div>
              {p.date && (
                <div className="mono" style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
                  {p.date}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}
