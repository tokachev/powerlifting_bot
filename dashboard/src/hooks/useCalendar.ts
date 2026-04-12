import { useQuery } from '@tanstack/react-query'
import { fetchCalendar } from '@/api/client'

export function useCalendar(userId: number, since: string, until: string) {
  return useQuery({
    queryKey: ['calendar', userId, since, until],
    queryFn: () => fetchCalendar(userId, since, until),
    enabled: userId > 0,
  })
}
