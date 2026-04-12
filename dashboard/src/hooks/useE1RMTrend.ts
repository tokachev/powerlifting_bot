import { useQuery } from '@tanstack/react-query'
import { fetchE1RMTrend } from '@/api/client'

export function useE1RMTrend(
  userId: number,
  exercises: string[],
  since: string,
  until: string,
) {
  return useQuery({
    queryKey: ['e1rm', userId, exercises, since, until],
    queryFn: () => fetchE1RMTrend(userId, exercises, since, until),
    enabled: userId > 0 && exercises.length > 0,
  })
}
