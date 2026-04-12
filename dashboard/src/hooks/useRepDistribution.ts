import { useQuery } from '@tanstack/react-query'
import { fetchRepDistribution } from '@/api/client'

export function useRepDistribution(
  userId: number,
  since: string,
  until: string,
  canonicalName?: string,
) {
  return useQuery({
    queryKey: ['rep-distribution', userId, since, until, canonicalName],
    queryFn: () => fetchRepDistribution(userId, since, until, canonicalName),
    enabled: userId > 0,
  })
}
