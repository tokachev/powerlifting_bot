"""Pydantic schemas for powerlifting dashboard endpoints."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Lift = Literal["squat", "bench", "deadlift"]


class Big3LiftCard(BaseModel):
    lift: Lift
    canonical_name: str
    current_e1rm_kg: float
    prev_e1rm_kg: float
    delta_pct: float
    pr_kg: float
    target_kg: float
    pct_of_bw: float | None
    sessions_28d: int


class LiftWeekPoint(BaseModel):
    iso_week: str
    e1rm_kg: float
    tonnage_kg: float
    intensity_pct: float | None
    avg_velocity_ms: float | None
    phase: str  # phase_name covering this week


class RecentSessionItem(BaseModel):
    date: date
    focus: str
    top_set_kg: float
    top_set_reps: int
    total_volume_kg: float
    avg_rpe: float | None
    duration_min: int | None


class AccessoryItem(BaseModel):
    canonical_name: str
    e1rm_kg: float
    delta_kg: float
    sets_28d: int
    top_set_kg: float


class NiggleItem(BaseModel):
    id: int
    recorded_date: date
    body_area: str
    severity: str
    note: str | None


class ReadinessDayPoint(BaseModel):
    date: date
    sleep_hours: float | None
    hrv_ms: float | None
    rhr_bpm: int | None
    recovery_pct: int | None


class ReadinessSummary(BaseModel):
    points: list[ReadinessDayPoint]
    avg_sleep_hours: float | None
    avg_hrv_ms: float | None
    avg_rhr_bpm: float | None
    latest_recovery_pct: int | None


class CalendarCell(BaseModel):
    date: date
    intensity: int  # 0..4


class BodyweightPoint(BaseModel):
    date: date
    weight_kg: float


class NextMeetEchoSchema(BaseModel):
    meet_date: date
    days_left: int
    name: str
    category: str | None
    federation: str | None
    target_squat_kg: float
    target_bench_kg: float
    target_deadlift_kg: float
    target_total_kg: float
    attempts_kg: dict[str, list[float]]


class PhaseSchema(BaseModel):
    phase_name: str
    start_date: date
    end_date: date
    color_hex: str | None


class KpiStripData(BaseModel):
    total_kg: float
    wilks: float | None
    dots: float | None
    bodyweight_kg: float | None
    next_meet_days_left: int | None


class OverviewResponse(BaseModel):
    kpi: KpiStripData
    big3: list[Big3LiftCard]
    tonnage_by_lift: dict[str, list[LiftWeekPoint]]  # {squat:[...], bench:[...], deadlift:[...]}
    intensity_by_lift: dict[str, list[LiftWeekPoint]]
    calendar: list[CalendarCell]
    readiness: ReadinessSummary
    next_meet: NextMeetEchoSchema | None
    accessories: list[AccessoryItem]
    niggles: list[NiggleItem]
    bodyweight_trend: list[BodyweightPoint]
    recent_sessions: list[RecentSessionItem]
    phases: list[PhaseSchema]


class RepMaxEntry(BaseModel):
    reps: int
    weight_kg: float


class SetRecommendationItem(BaseModel):
    name: str
    scheme: str
    intensity_pct: int
    weight_kg: float


class PRItemSchema(BaseModel):
    date: date
    weight_kg: float
    reps: int
    estimated_1rm_kg: float
    is_meet: bool  # true if the PR date matches a meet


class TechniqueNoteItem(BaseModel):
    id: int
    recorded_date: date
    note_text: str
    source: str


class AcwrSchema(BaseModel):
    acute_7d_kg: float
    chronic_28d_avg_kg: float
    ratio: float
    risk_zone: str


class LiftDetailResponse(BaseModel):
    lift: Lift
    canonical_name: str
    current_e1rm_kg: float
    prev_e1rm_kg: float
    delta_pct: float
    pr_kg: float
    target_kg: float
    pct_of_bw: float | None
    weekly: list[LiftWeekPoint]
    rep_max: list[RepMaxEntry]
    set_recommendations: list[SetRecommendationItem]
    all_prs: list[PRItemSchema]
    technique_notes: list[TechniqueNoteItem]
    acwr: AcwrSchema


class MeetEntrySchema(BaseModel):
    id: int
    date: date
    name: str
    category: str | None
    federation: str | None
    bodyweight_kg: float | None
    squat_kg: float
    bench_kg: float
    deadlift_kg: float
    total_kg: float
    wilks: float | None
    dots: float | None
    ipf_gl: float | None
    place: int | None
    is_gym_meet: bool


class RmGrowthItem(BaseModel):
    lift: Lift
    start_kg: float
    end_kg: float
    delta_kg: float
    delta_pct: float


class PersonalRecordCard(BaseModel):
    lift: Lift
    canonical_name: str
    weight_kg: float
    date: date | None


class HistoryKpiSchema(BaseModel):
    total_meets: int
    best_total_kg: float
    best_total_at: date | None
    best_wilks: float | None
    best_dots: float | None
    podiums: int


class HistoryResponse(BaseModel):
    kpi: HistoryKpiSchema
    meets: list[MeetEntrySchema]
    rm_growth: list[RmGrowthItem]
    personal_records: list[PersonalRecordCard]
    best_total_kg: float
    best_gym_total_kg: float


# -------------------------- write request schemas


class MeetCreate(BaseModel):
    meet_date: date
    name: str = Field(min_length=1)
    category: str | None = None
    federation: str | None = None
    bodyweight_kg: float | None = Field(default=None, ge=30, le=250)
    squat_kg: float = Field(ge=0, le=600)
    bench_kg: float = Field(ge=0, le=400)
    deadlift_kg: float = Field(ge=0, le=600)
    place: int | None = None
    is_gym_meet: bool = False
    notes: str | None = None
    is_female: bool = False


class RecoveryCreate(BaseModel):
    recorded_date: date
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    hrv_ms: float | None = Field(default=None, ge=0, le=300)
    rhr_bpm: int | None = Field(default=None, ge=20, le=200)
    recovery_pct: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = None


class NiggleCreate(BaseModel):
    recorded_date: date
    body_area: str = Field(min_length=1)
    severity: Literal["good", "warn", "crit"]
    note: str | None = None


class NextMeetUpdate(BaseModel):
    meet_date: date
    name: str = Field(min_length=1)
    category: str | None = None
    federation: str | None = None
    target_squat_kg: float = Field(ge=0, le=600)
    target_bench_kg: float = Field(ge=0, le=400)
    target_deadlift_kg: float = Field(ge=0, le=600)
    attempts_kg: dict[str, list[float]] = Field(
        default_factory=lambda: {"squat": [], "bench": [], "deadlift": []}
    )


class BodyweightCreate(BaseModel):
    recorded_date: date
    weight_kg: float = Field(ge=30, le=250)
