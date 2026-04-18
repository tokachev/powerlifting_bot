import { http } from './client'
import type {
  HistoryResponse,
  Lift,
  LiftDetailResponse,
  OverviewResponse,
} from './pl_types'

export async function fetchOverview(userId: number, weeks = 14): Promise<OverviewResponse> {
  const r = await http.get<OverviewResponse>(
    `/api/pl/overview?user_id=${userId}&weeks=${weeks}`,
  )
  return r.data
}

export async function fetchLiftDetail(
  userId: number,
  lift: Lift,
  weeks = 14,
): Promise<LiftDetailResponse> {
  const r = await http.get<LiftDetailResponse>(
    `/api/pl/lift/${lift}?user_id=${userId}&weeks=${weeks}`,
  )
  return r.data
}

export async function fetchHistory(userId: number): Promise<HistoryResponse> {
  const r = await http.get<HistoryResponse>(`/api/pl/history?user_id=${userId}`)
  return r.data
}

export async function createMeet(userId: number, body: unknown): Promise<{ id: number }> {
  const r = await http.post<{ id: number }>(`/api/pl/meets?user_id=${userId}`, body)
  return r.data
}

export async function createRecovery(userId: number, body: unknown): Promise<{ id: number }> {
  const r = await http.post<{ id: number }>(`/api/pl/recovery?user_id=${userId}`, body)
  return r.data
}

export async function createNiggle(userId: number, body: unknown): Promise<{ id: number }> {
  const r = await http.post<{ id: number }>(`/api/pl/niggles?user_id=${userId}`, body)
  return r.data
}

export async function updateNextMeet(userId: number, body: unknown): Promise<void> {
  await http.put(`/api/pl/next-meet?user_id=${userId}`, body)
}

export async function createBodyweight(userId: number, body: unknown): Promise<void> {
  await http.post(`/api/pl/bodyweight?user_id=${userId}`, body)
}
