import { useEffect, useMemo, useState } from 'react'
import { format, subDays } from 'date-fns'
import { Sidebar } from '@/components/Sidebar'
import { StatsCards } from '@/components/StatsCards'
import { KpshStackedBar } from '@/components/KpshStackedBar'
import { IntensityLine } from '@/components/IntensityLine'
import { KpshByMuscleBar } from '@/components/KpshByMuscleBar'
import { KpshByPatternBar } from '@/components/KpshByPatternBar'
import { E1RMTrend } from '@/components/E1RMTrend'
import { useDashboard } from '@/hooks/useDashboard'
import { useE1RMTrend } from '@/hooks/useE1RMTrend'
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

  const defaultE1RMExercises = ['back_squat', 'bench_press', 'deadlift']
  const e1rmSince = format(subDays(new Date(), 89), 'yyyy-MM-dd')
  const e1rmUntil = format(new Date(), 'yyyy-MM-dd')
  const { data: e1rmData } = useE1RMTrend(
    query.user_id, defaultE1RMExercises, e1rmSince, e1rmUntil,
  )

  const headerInfo = useMemo(() => {
    if (!data) return null
    return `${data.filters.since} → ${data.filters.until}, ${data.total_workouts} тренировок`
  }, [data])

  return (
    <div className="flex h-full">
      <Sidebar value={query} onChange={setQuery} />
      <main className="flex-1 overflow-y-auto p-8 space-y-6 animate-fade-in">
        <header className="flex items-baseline justify-between pb-6 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-2 h-8 rounded-full bg-accent" />
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-accent-light">pwrbot</span>
              <span className="text-neutral-500 mx-2">&middot;</span>
              <span>Dashboard</span>
            </h1>
          </div>
          {headerInfo && (
            <span className="text-sm text-neutral-500 font-medium bg-white/[0.03] px-3 py-1 rounded-lg border border-white/[0.06]">
              {headerInfo}
            </span>
          )}
        </header>

        {!enabled && (
          <div className="text-neutral-500 text-sm">Выбери пользователя в сайдбаре.</div>
        )}

        {enabled && isLoading && (
          <div className="text-neutral-500 text-sm animate-pulse">Загрузка...</div>
        )}

        {enabled && isError && (
          <div className="text-red-400 text-sm">
            Ошибка: {(error as Error)?.message ?? 'unknown'}
          </div>
        )}

        {enabled && data && (
          <>
            <StatsCards data={data} />
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
              <KpshStackedBar data={data} />
              <IntensityLine data={data} />
              <KpshByMuscleBar data={data} />
              <KpshByPatternBar data={data} />
            </div>
            {e1rmData && <E1RMTrend data={e1rmData} />}
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
