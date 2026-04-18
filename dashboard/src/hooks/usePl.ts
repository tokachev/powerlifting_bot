import { useQuery } from '@tanstack/react-query'
import { fetchHistory, fetchLiftDetail, fetchOverview } from '@/api/pl_client'
import type { Lift } from '@/api/pl_types'

export function useOverview(userId: number, weeks = 14) {
  return useQuery({
    queryKey: ['pl', 'overview', userId, weeks],
    queryFn: () => fetchOverview(userId, weeks),
    enabled: userId > 0,
  })
}

export function useLiftDetail(userId: number, lift: Lift, weeks = 14) {
  return useQuery({
    queryKey: ['pl', 'lift', userId, lift, weeks],
    queryFn: () => fetchLiftDetail(userId, lift, weeks),
    enabled: userId > 0,
  })
}

export function useHistory(userId: number) {
  return useQuery({
    queryKey: ['pl', 'history', userId],
    queryFn: () => fetchHistory(userId),
    enabled: userId > 0,
  })
}
