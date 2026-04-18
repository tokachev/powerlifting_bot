import { useTranslation } from 'react-i18next'
import type { HistoryKpi } from '@/api/pl_types'

export function HistoryKpiStrip({ kpi }: { kpi: HistoryKpi }) {
  const { t } = useTranslation()
  const cells = [
    { label: t('meets'), value: String(kpi.total_meets), unit: '' },
    {
      label: t('bestTotal'),
      value: kpi.best_total_kg.toFixed(1),
      unit: t('kg'),
      meta: kpi.best_total_at,
    },
    { label: t('wilks'), value: kpi.best_wilks?.toFixed(1) ?? '—', unit: '' },
    { label: t('dots'), value: kpi.best_dots?.toFixed(1) ?? '—', unit: '' },
    {
      label: t('podiums'),
      value: String(kpi.podiums),
      unit: `/${kpi.total_meets}`,
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
          {c.meta && <div className="kpi-meta mono">{c.meta}</div>}
        </div>
      ))}
    </div>
  )
}
