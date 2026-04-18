import { useTranslation } from 'react-i18next'
import type { CalendarCell } from '@/api/pl_types'
import { Card } from '../shared'

export function TrainingCalendar({ cells }: { cells: CalendarCell[] }) {
  const { t } = useTranslation()
  // cells are 112 daily entries sorted ascending. group into 16 weeks × 7 days.
  // Each column = one week (mon..sun).
  return (
    <Card title={t('calendar')} meta="16W">
      <div className="heat" role="img" aria-label="training calendar">
        {cells.map((c) => (
          <span key={c.date} data-v={c.intensity > 0 ? c.intensity : undefined} title={c.date} />
        ))}
      </div>
    </Card>
  )
}
