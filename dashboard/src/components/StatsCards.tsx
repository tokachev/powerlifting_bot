import type { DashboardResponse } from '@/api/types'

interface Props {
  data: DashboardResponse
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
      <div className="text-xs uppercase tracking-wider text-neutral-400">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  )
}

export function StatsCards({ data }: Props) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <Card label="Тренировок" value={String(data.total_workouts)} />
      <Card label="КПШ всего" value={String(data.total_kpsh)} />
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
