import { useQuery } from '@tanstack/react-query'
import { fetchWeeklySets } from '@/api/client'

export function useWeeklySets(userId: number, since: string, until: string) {
  return useQuery({
    queryKey: ['weekly-sets', userId, since, until],
    queryFn: () => fetchWeeklySets(userId, since, until),
    enabled: userId > 0,
  })
}
