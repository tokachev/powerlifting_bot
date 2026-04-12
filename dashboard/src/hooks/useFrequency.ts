import { useQuery } from '@tanstack/react-query'
import { fetchFrequency } from '@/api/client'

export function useFrequency(userId: number, since: string, until: string) {
  return useQuery({
    queryKey: ['frequency', userId, since, until],
    queryFn: () => fetchFrequency(userId, since, until),
    enabled: userId > 0,
  })
}
