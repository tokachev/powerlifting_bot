import { useTranslation } from 'react-i18next'
import type { KpiStripData, NextMeetEcho } from '@/api/pl_types'

export function KpiStrip({
  kpi,
  nextMeet,
}: {
  kpi: KpiStripData
  nextMeet: NextMeetEcho | null
}) {
  const { t } = useTranslation()
  const cells = [
    { label: t('total'), value: kpi.total_kg.toFixed(1), unit: t('kg') },
    { label: t('wilks'), value: kpi.wilks?.toFixed(1) ?? '—', unit: '' },
    { label: t('dots'), value: kpi.dots?.toFixed(1) ?? '—', unit: '' },
    { label: t('bodyweight'), value: kpi.bodyweight_kg?.toFixed(1) ?? '—', unit: t('kg') },
    {
      label: t('nextMeet'),
      value: nextMeet ? String(nextMeet.days_left) : '—',
      unit: nextMeet ? t('daysOutShort') : '',
    },
  ]
  return (
    <div className="kpi-strip">
      {cells.map((c, i) => (
        <div key={i} className="kpi">
          <div className="kpi-label">{c.label}</div>
          <div className="kpi-value mono tabular">
            {c.value}
            {c.unit && <span className="unit"> {c.unit}</span>}
          </div>
          {i === 4 && nextMeet && (
            <div className="kpi-meta mono">{nextMeet.name}</div>
          )}
        </div>
      ))}
    </div>
  )
}
