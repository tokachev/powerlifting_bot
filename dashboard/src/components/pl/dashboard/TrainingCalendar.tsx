import { useTranslation } from 'react-i18next'
import type { CalendarCell } from '@/api/pl_types'
import { Card } from '../shared'

function buildTooltip(
  c: CalendarCell,
  t: (key: string) => string,
  locale: string,
): string {
  const lines: string[] = []
  const parsed = new Date(`${c.date}T00:00:00`)
  const dateLabel = isNaN(parsed.getTime())
    ? c.date
    : parsed.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
  lines.push(dateLabel)
  const formatKg = (value: number) =>
    value.toLocaleString(locale, { maximumFractionDigits: 1 })
  if (c.tonnage_kg > 0) {
    lines.push(`${t('tonnage')}: ${formatKg(c.tonnage_kg)} ${t('kg')}`)
  }
  const lifts: Array<[string, number | null]> = [
    ['squat', c.max_squat_kg],
    ['bench', c.max_bench_kg],
    ['deadlift', c.max_deadlift_kg],
  ]
  for (const [key, value] of lifts) {
    if (value != null) {
      lines.push(`${t(key)}: ${formatKg(value)} ${t('kg')}`)
    }
  }
  return lines.join('\n')
}

export function TrainingCalendar({ cells }: { cells: CalendarCell[] }) {
  const { t, i18n } = useTranslation()
  return (
    <Card title={t('calendar')} meta="16W">
      <div className="heat" role="img" aria-label="training calendar">
        {cells.map((c) => (
          <span
            key={c.date}
            data-v={c.intensity > 0 ? c.intensity : undefined}
            title={buildTooltip(c, t, i18n.language)}
          />
        ))}
      </div>
    </Card>
  )
}
