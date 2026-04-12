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

// ------------------------------------------------------------------ e1rm trend

export interface E1RMPoint {
  date: string
  canonical_name: string
  estimated_1rm_kg: number
  best_weight_kg: number
  best_reps: number
}

export interface E1RMTrendResponse {
  points: E1RMPoint[]
}

export const E1RM_EXERCISE_COLORS: Record<string, string> = {
  back_squat: '#f97316',
  bench_press: '#3b82f6',
  deadlift: '#ef4444',
}

export const E1RM_EXERCISE_LABELS: Record<string, string> = {
  back_squat: 'Присед',
  bench_press: 'Жим лёжа',
  deadlift: 'Становая',
}

// ------------------------------------------------------------------ weekly sets

export interface WeeklySetsBucket {
  iso_week: string
  muscle_group: string
  hard_sets: number
}

export interface VolumeLandmark {
  mev: number
  mav: number
  mrv: number
}

export interface WeeklySetsResponse {
  buckets: WeeklySetsBucket[]
  landmarks: Record<string, VolumeLandmark>
}

// ------------------------------------------------------------------ tonnage trend

export interface TonnageWeek {
  iso_week: string
  tonnage_kg: number
}

export interface TonnageTrendResponse {
  weeks: TonnageWeek[]
}

// ------------------------------------------------------------------ calendar

export interface CalendarDay {
  date: string
  workout_count: number
  total_sets: number
  total_tonnage_kg: number
}

export interface CalendarResponse {
  days: CalendarDay[]
}

// ------------------------------------------------------------------ personal records

export interface PersonalRecord {
  date: string
  canonical_name: string
  pr_type: string
  weight_kg: number
  reps: number
  estimated_1rm_kg: number
  previous_1rm_kg: number | null
}

export interface PRsResponse {
  records: PersonalRecord[]
}

// ------------------------------------------------------------------ per-exercise detail

export interface SetDetail {
  reps: number
  weight_kg: number
  rpe: number | null
  is_warmup: boolean
  estimated_1rm_kg: number | null
}

export interface ExerciseSession {
  date: string
  best_e1rm_kg: number
  total_volume_kg: number
  sets: SetDetail[]
}

export interface PerExerciseResponse {
  sessions: ExerciseSession[]
}

// ------------------------------------------------------------------ rep distribution

export interface RepBucket {
  rep_range: string
  set_count: number
  rep_count: number
}

export interface RepDistributionResponse {
  buckets: RepBucket[]
}

// ------------------------------------------------------------------ frequency

export interface FrequencyCell {
  iso_week: string
  muscle_group: string
  sessions: number
}

export interface FrequencyResponse {
  cells: FrequencyCell[]
}

export const MUSCLE_GROUP_COLORS: Record<string, string> = {
  legs: '#3b82f6',
  chest: '#ef4444',
  back: '#22c55e',
  shoulders: '#f97316',
  arms: '#a78bfa',
  core: '#fbbf24',
}
