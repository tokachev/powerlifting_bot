import { useQuery } from '@tanstack/react-query'
import { fetchPerExercise } from '@/api/client'

export function usePerExercise(
  userId: number,
  exercise: string,
  since: string,
  until: string,
) {
  return useQuery({
    queryKey: ['per-exercise', userId, exercise, since, until],
    queryFn: () => fetchPerExercise(userId, exercise, since, until),
    enabled: userId > 0 && exercise.length > 0,
  })
}
