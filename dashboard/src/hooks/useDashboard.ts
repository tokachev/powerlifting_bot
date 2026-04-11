import { useQuery } from '@tanstack/react-query'
import { fetchDashboard } from '@/api/client'
import type { DashboardQuery } from '@/api/types'

export function useDashboard(query: DashboardQuery, enabled: boolean) {
  return useQuery({
    queryKey: ['dashboard', query],
    queryFn: () => fetchDashboard(query),
    enabled,
  })
}
