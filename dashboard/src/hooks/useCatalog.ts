import { useQuery } from '@tanstack/react-query'
import { fetchCatalog } from '@/api/client'

export function useCatalog() {
  return useQuery({
    queryKey: ['catalog'],
    queryFn: fetchCatalog,
    staleTime: 5 * 60_000,
  })
}
