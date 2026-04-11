import { useQuery } from '@tanstack/react-query'
import { fetchUsers } from '@/api/client'

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: fetchUsers,
  })
}
