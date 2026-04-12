import axios from 'axios'
import type {
  CalendarResponse,
  DashboardQuery,
  DashboardResponse,
  E1RMTrendResponse,
  ExerciseInfo,
  PRsResponse,
  TonnageTrendResponse,
  UserInfo,
  WeeklySetsResponse,
} from './types'

export const http = axios.create({
  baseURL: '',
  timeout: 15_000,
})

export async function fetchUsers(): Promise<UserInfo[]> {
  const r = await http.get<UserInfo[]>('/api/users')
  return r.data
}

export async function fetchCatalog(): Promise<ExerciseInfo[]> {
  const r = await http.get<ExerciseInfo[]>('/api/catalog')
  return r.data
}

export async function fetchDashboard(q: DashboardQuery): Promise<DashboardResponse> {
  const params = new URLSearchParams()
  params.append('user_id', String(q.user_id))
  params.append('since', q.since)
  params.append('until', q.until)
  params.append('target_only', String(q.target_only))
  for (const m of q.muscle_groups) params.append('muscle_groups', m)
  for (const m of q.movement_patterns) params.append('movement_patterns', m)
  const r = await http.get<DashboardResponse>(`/api/dashboard?${params.toString()}`)
  return r.data
}

export async function fetchE1RMTrend(
  userId: number,
  exercises: string[],
  since: string,
  until: string,
): Promise<E1RMTrendResponse> {
  const params = new URLSearchParams()
  params.append('user_id', String(userId))
  params.append('since', since)
  params.append('until', until)
  for (const e of exercises) params.append('exercises', e)
  const r = await http.get<E1RMTrendResponse>(`/api/e1rm?${params.toString()}`)
  return r.data
}

export async function fetchWeeklySets(
  userId: number,
  since: string,
  until: string,
): Promise<WeeklySetsResponse> {
  const params = new URLSearchParams()
  params.append('user_id', String(userId))
  params.append('since', since)
  params.append('until', until)
  const r = await http.get<WeeklySetsResponse>(`/api/weekly-sets?${params.toString()}`)
  return r.data
}

export async function fetchTonnageTrend(
  userId: number,
  since: string,
  until: string,
): Promise<TonnageTrendResponse> {
  const params = new URLSearchParams()
  params.append('user_id', String(userId))
  params.append('since', since)
  params.append('until', until)
  const r = await http.get<TonnageTrendResponse>(`/api/tonnage-trend?${params.toString()}`)
  return r.data
}

export async function fetchCalendar(
  userId: number,
  since: string,
  until: string,
): Promise<CalendarResponse> {
  const params = new URLSearchParams()
  params.append('user_id', String(userId))
  params.append('since', since)
  params.append('until', until)
  const r = await http.get<CalendarResponse>(`/api/calendar?${params.toString()}`)
  return r.data
}

export async function fetchPRs(
  userId: number,
  limit: number = 20,
): Promise<PRsResponse> {
  const r = await http.get<PRsResponse>(`/api/prs?user_id=${userId}&limit=${limit}`)
  return r.data
}
