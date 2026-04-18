import { useTranslation } from 'react-i18next'
import type { MeetEntry } from '@/api/pl_types'
import { Card, Chip, EmptyState } from '../shared'

export function MeetHistoryTable({ meets, bestTotal }: { meets: MeetEntry[]; bestTotal: number }) {
  const { t } = useTranslation()
  if (meets.length === 0) {
    return (
      <Card title={t('meetHistory')}>
        <EmptyState text={t('noMeets')} />
      </Card>
    )
  }
  return (
    <Card title={t('meetHistory')}>
      <table className="tbl">
        <thead>
          <tr>
            <th>{t('date')}</th>
            <th>{t('meet')}</th>
            <th>{t('squat')}</th>
            <th>{t('bench')}</th>
            <th>{t('deadlift')}</th>
            <th>{t('total')}</th>
            <th>{t('wilks')}</th>
            <th>{t('place')}</th>
          </tr>
        </thead>
        <tbody>
          {meets.map((m) => (
            <tr key={m.id}>
              <td className="num">{m.date}</td>
              <td>
                {m.name}{' '}
                {m.is_gym_meet && <span className="muted" style={{ fontSize: 10 }}>gym</span>}
              </td>
              <td className="num">{m.squat_kg.toFixed(1)}</td>
              <td className="num">{m.bench_kg.toFixed(1)}</td>
              <td className="num">{m.deadlift_kg.toFixed(1)}</td>
              <td
                className="num"
                style={m.total_kg === bestTotal ? { color: 'var(--accent)', fontWeight: 600 } : undefined}
              >
                {m.total_kg.toFixed(1)}
              </td>
              <td className="num">{m.wilks?.toFixed(1) ?? '—'}</td>
              <td>{m.place ? <Chip>{m.place}</Chip> : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
