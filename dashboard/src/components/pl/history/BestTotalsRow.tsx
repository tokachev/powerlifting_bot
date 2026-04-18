import { useTranslation } from 'react-i18next'
import { Card } from '../shared'

export function BestTotalsRow({
  bestTotalKg,
  bestGymTotalKg,
}: {
  bestTotalKg: number
  bestGymTotalKg: number
}) {
  const { t } = useTranslation()
  return (
    <div className="row cols-2">
      <Card title={t('bestTotal')}>
        <div
          className="mono tabular"
          style={{ fontSize: 38, fontWeight: 700, color: 'var(--accent)' }}
        >
          {bestTotalKg.toFixed(1)}
          <span style={{ fontSize: 14, color: 'var(--fg-2)', marginLeft: 6 }}>{t('kg')}</span>
        </div>
      </Card>
      <Card title={t('bestGymTotal')}>
        <div
          className="mono tabular"
          style={{ fontSize: 38, fontWeight: 700, color: 'var(--fg)' }}
        >
          {bestGymTotalKg.toFixed(1)}
          <span style={{ fontSize: 14, color: 'var(--fg-2)', marginLeft: 6 }}>{t('kg')}</span>
        </div>
      </Card>
    </div>
  )
}
