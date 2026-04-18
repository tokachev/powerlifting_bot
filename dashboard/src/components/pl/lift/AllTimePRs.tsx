import { useTranslation } from 'react-i18next'
import type { PRItem } from '@/api/pl_types'
import { Card, Chip, EmptyState } from '../shared'

export function AllTimePRs({ items }: { items: PRItem[] }) {
  const { t } = useTranslation()
  if (items.length === 0) {
    return (
      <Card title={t('allTimePr')}>
        <EmptyState text={t('noData')} />
      </Card>
    )
  }
  return (
    <Card title={t('allTimePr')} meta={`${items.length}`}>
      <table className="tbl">
        <thead>
          <tr>
            <th>{t('date')}</th>
            <th>{t('kg')}×{t('sets')}</th>
            <th>{t('e1rm')}</th>
            <th>{t('rpe')}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((p, i) => (
            <tr key={i}>
              <td className="num">{p.date}</td>
              <td className="num">
                {p.weight_kg.toFixed(1)}×{p.reps}
              </td>
              <td className="num">{p.estimated_1rm_kg.toFixed(1)}</td>
              <td className="muted"></td>
              <td>
                {p.is_meet ? <Chip kind="good">MEET</Chip> : <Chip>GYM</Chip>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
