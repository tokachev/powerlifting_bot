import { useQuery } from '@tanstack/react-query'
import { fetchTonnageTrend } from '@/api/client'

export function useTonnageTrend(userId: number, since: string, until: string) {
  return useQuery({
    queryKey: ['tonnage-trend', userId, since, until],
    queryFn: () => fetchTonnageTrend(userId, since, until),
    enabled: userId > 0,
  })
}
