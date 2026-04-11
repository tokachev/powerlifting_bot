import { useEffect, useMemo, useState } from 'react'
import { format, subDays } from 'date-fns'
import { Sidebar } from '@/components/Sidebar'
import { StatsCards } from '@/components/StatsCards'
import { KpshStackedBar } from '@/components/KpshStackedBar'
import { IntensityLine } from '@/components/IntensityLine'
import { KpshByMuscleBar } from '@/components/KpshByMuscleBar'
import { KpshByPatternBar } from '@/components/KpshByPatternBar'
import { useDashboard } from '@/hooks/useDashboard'
import { useUsers } from '@/hooks/useUsers'
import type { DashboardQuery } from '@/api/types'

function defaultQuery(): DashboardQuery {
  const today = new Date()
  return {
    user_id: 0,
    since: format(subDays(today, 27), 'yyyy-MM-dd'),
    until: format(today, 'yyyy-MM-dd'),
    muscle_groups: [],
    movement_patterns: [],
    target_only: false,
  }
}

export default function Dashboard() {
  const [query, setQuery] = useState<DashboardQuery>(defaultQuery)
  const { data: users } = useUsers()

  // Auto-select first user once they load.
  useEffect(() => {
    if (query.user_id === 0 && users && users.length > 0) {
      setQuery((q) => ({ ...q, user_id: users[0].id }))
    }
  }, [users, query.user_id])

  const enabled = query.user_id > 0
  const { data, isLoading, isError, error } = useDashboard(query, enabled)

  const headerInfo = useMemo(() => {
    if (!data) return null
    return `${data.filters.since} → ${data.filters.until}, ${data.total_workouts} тренировок`
  }, [data])

  return (
    <div className="flex h-full">
      <Sidebar value={query} onChange={setQuery} />
      <main className="flex-1 overflow-y-auto p-6 space-y-4">
        <header className="flex items-baseline justify-between">
          <h1 className="text-xl font-semibold">pwrbot · Dashboard</h1>
          {headerInfo && <span className="text-sm text-neutral-400">{headerInfo}</span>}
        </header>

        {!enabled && (
          <div className="text-neutral-400 text-sm">Выбери пользователя в сайдбаре.</div>
        )}

        {enabled && isLoading && (
          <div className="text-neutral-400 text-sm">Загрузка…</div>
        )}

        {enabled && isError && (
          <div className="text-red-400 text-sm">
            Ошибка: {(error as Error)?.message ?? 'unknown'}
          </div>
        )}

        {enabled && data && (
          <>
            <StatsCards data={data} />
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <KpshStackedBar data={data} />
              <IntensityLine data={data} />
              <KpshByMuscleBar data={data} />
              <KpshByPatternBar data={data} />
            </div>
            {data.total_workouts === 0 && (
              <div className="text-neutral-500 text-sm">
                Нет тренировок за выбранный период.
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
