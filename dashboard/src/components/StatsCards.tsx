import clsx from 'clsx'
import type { DashboardResponse } from '@/api/types'

interface Props {
  data: DashboardResponse
}

function Card({
  label,
  value,
  accent = false,
}: {
  label: string
  value: string
  accent?: boolean
}) {
  return (
    <div
      className={clsx(
        'glass-card',
        accent && 'border-accent/20 shadow-glow-sm bg-gradient-to-br from-accent/[0.08] to-accent/[0.02]',
      )}
    >
      <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-medium">
        {label}
      </div>
      <div
        className={clsx(
          'text-3xl font-bold mt-2 tracking-tight',
          accent ? 'text-accent-light' : 'text-neutral-100',
        )}
      >
        {value}
      </div>
    </div>
  )
}

export function StatsCards({ data }: Props) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card label="Тренировок" value={String(data.total_workouts)} />
      <Card label="КПШ всего" value={String(data.total_kpsh)} accent />
      <Card
        label="Средняя интенсивность"
        value={
          data.avg_intensity_kg !== null ? `${data.avg_intensity_kg.toFixed(1)} кг` : '—'
        }
      />
      <Card label="Дней в окне" value={String(data.days.length)} />
    </div>
  )
}
