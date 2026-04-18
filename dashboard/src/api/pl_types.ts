export type Lift = 'squat' | 'bench' | 'deadlift'

export interface Big3LiftCard {
  lift: Lift
  canonical_name: string
  current_e1rm_kg: number
  prev_e1rm_kg: number
  delta_pct: number
  pr_kg: number
  target_kg: number
  pct_of_bw: number | null
  sessions_28d: number
}

export interface LiftWeekPoint {
  iso_week: string
  e1rm_kg: number
  tonnage_kg: number
  intensity_pct: number | null
  avg_velocity_ms: number | null
  phase: string
}

export interface RecentSessionItem {
  date: string
  focus: string
  top_set_kg: number
  top_set_reps: number
  total_volume_kg: number
  avg_rpe: number | null
  duration_min: number | null
}

export interface AccessoryItem {
  canonical_name: string
  e1rm_kg: number
  delta_kg: number
  sets_28d: number
  top_set_kg: number
}

export interface NiggleItem {
  id: number
  recorded_date: string
  body_area: string
  severity: 'good' | 'warn' | 'crit'
  note: string | null
}

export interface ReadinessDayPoint {
  date: string
  sleep_hours: number | null
  hrv_ms: number | null
  rhr_bpm: number | null
  recovery_pct: number | null
}

export interface ReadinessSummary {
  points: ReadinessDayPoint[]
  avg_sleep_hours: number | null
  avg_hrv_ms: number | null
  avg_rhr_bpm: number | null
  latest_recovery_pct: number | null
}

export interface CalendarCell {
  date: string
  intensity: number
}

export interface BodyweightPoint {
  date: string
  weight_kg: number
}

export interface NextMeetEcho {
  meet_date: string
  days_left: number
  name: string
  category: string | null
  federation: string | null
  target_squat_kg: number
  target_bench_kg: number
  target_deadlift_kg: number
  target_total_kg: number
  attempts_kg: Record<string, number[]>
}

export interface PhaseItem {
  phase_name: string
  start_date: string
  end_date: string
  color_hex: string | null
}

export interface KpiStripData {
  total_kg: number
  wilks: number | null
  dots: number | null
  bodyweight_kg: number | null
  next_meet_days_left: number | null
}

export interface OverviewResponse {
  kpi: KpiStripData
  big3: Big3LiftCard[]
  tonnage_by_lift: Record<Lift, LiftWeekPoint[]>
  intensity_by_lift: Record<Lift, LiftWeekPoint[]>
  calendar: CalendarCell[]
  readiness: ReadinessSummary
  next_meet: NextMeetEcho | null
  accessories: AccessoryItem[]
  niggles: NiggleItem[]
  bodyweight_trend: BodyweightPoint[]
  recent_sessions: RecentSessionItem[]
  phases: PhaseItem[]
}

export interface RepMaxEntry {
  reps: number
  weight_kg: number
}

export interface SetRecommendationItem {
  name: string
  scheme: string
  intensity_pct: number
  weight_kg: number
}

export interface PRItem {
  date: string
  weight_kg: number
  reps: number
  estimated_1rm_kg: number
  is_meet: boolean
}

export interface TechniqueNoteItem {
  id: number
  recorded_date: string
  note_text: string
  source: string
}

export interface Acwr {
  acute_7d_kg: number
  chronic_28d_avg_kg: number
  ratio: number
  risk_zone: 'low' | 'sweet' | 'high' | 'danger'
}

export interface LiftDetailResponse {
  lift: Lift
  canonical_name: string
  current_e1rm_kg: number
  prev_e1rm_kg: number
  delta_pct: number
  pr_kg: number
  target_kg: number
  pct_of_bw: number | null
  weekly: LiftWeekPoint[]
  rep_max: RepMaxEntry[]
  set_recommendations: SetRecommendationItem[]
  all_prs: PRItem[]
  technique_notes: TechniqueNoteItem[]
  acwr: Acwr
}

export interface MeetEntry {
  id: number
  date: string
  name: string
  category: string | null
  federation: string | null
  bodyweight_kg: number | null
  squat_kg: number
  bench_kg: number
  deadlift_kg: number
  total_kg: number
  wilks: number | null
  dots: number | null
  ipf_gl: number | null
  place: number | null
  is_gym_meet: boolean
}

export interface RmGrowthItem {
  lift: Lift
  start_kg: number
  end_kg: number
  delta_kg: number
  delta_pct: number
}

export interface PersonalRecordCard {
  lift: Lift
  canonical_name: string
  weight_kg: number
  date: string | null
}

export interface HistoryKpi {
  total_meets: number
  best_total_kg: number
  best_total_at: string | null
  best_wilks: number | null
  best_dots: number | null
  podiums: number
}

export interface HistoryResponse {
  kpi: HistoryKpi
  meets: MeetEntry[]
  rm_growth: RmGrowthItem[]
  personal_records: PersonalRecordCard[]
  best_total_kg: number
  best_gym_total_kg: number
}
