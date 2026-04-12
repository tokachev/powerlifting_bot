import { useQuery } from '@tanstack/react-query'
import { fetchPRs } from '@/api/client'

export function usePRs(userId: number) {
  return useQuery({
    queryKey: ['prs', userId],
    queryFn: () => fetchPRs(userId),
    enabled: userId > 0,
  })
}
