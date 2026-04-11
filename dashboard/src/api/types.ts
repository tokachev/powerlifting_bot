// Mirror of pwrbot.api.schemas. Keep in sync manually.

export interface UserInfo {
  id: number
  telegram_id: number
  display_name: string | null
}

export interface ExerciseInfo {
  canonical_name: string
  movement_pattern: string
  target_group: string | null
  muscle_group: string | null
}

export type Bucket = 'squat' | 'bench' | 'deadlift' | 'other'

export interface DashboardFiltersEcho {
  user_id: number
  since: string
  until: string
  muscle_groups: string[]
  movement_patterns: string[]
  target_only: boolean
}

export interface DashboardResponse {
  days: string[]
  kpsh_by_bucket: Record<Bucket, number[]>
  intensity_kg: Array<number | null>
  kpsh_by_muscle: Record<string, number>
  kpsh_by_pattern: Record<string, number>
  total_workouts: number
  total_kpsh: number
  avg_intensity_kg: number | null
  filters: DashboardFiltersEcho
}

export interface DashboardQuery {
  user_id: number
  since: string // YYYY-MM-DD
  until: string // YYYY-MM-DD
  muscle_groups: string[]
  movement_patterns: string[]
  target_only: boolean
}

export const MUSCLE_GROUPS = ['legs', 'chest', 'back', 'shoulders', 'arms', 'core'] as const
export const MOVEMENT_PATTERNS = [
  'push',
  'pull',
  'squat',
  'hinge',
  'carry',
  'core',
  'accessory',
] as const
export const BUCKETS: readonly Bucket[] = ['squat', 'bench', 'deadlift', 'other']

export const BUCKET_COLORS: Record<Bucket, string> = {
  squat: '#3b82f6',
  bench: '#ef4444',
  deadlift: '#22c55e',
  other: '#6b7280',
}

export const BUCKET_LABELS: Record<Bucket, string> = {
  squat: 'Присед',
  bench: 'Жим',
  deadlift: 'Становая',
  other: 'Остальное',
}

export const MUSCLE_GROUP_LABELS: Record<string, string> = {
  legs: 'Ноги',
  chest: 'Грудь',
  back: 'Спина',
  shoulders: 'Плечи',
  arms: 'Руки',
  core: 'Кор',
}

export const MOVEMENT_PATTERN_LABELS: Record<string, string> = {
  push: 'Push',
  pull: 'Pull',
  squat: 'Squat',
  hinge: 'Hinge',
  carry: 'Carry',
  core: 'Core',
  accessory: 'Accessory',
}
