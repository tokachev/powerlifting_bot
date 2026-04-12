"""Pydantic response schemas for the dashboard API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class UserInfo(BaseModel):
    id: int
    telegram_id: int
    display_name: str | None


class ExerciseInfo(BaseModel):
    canonical_name: str
    movement_pattern: str
    target_group: str | None
    muscle_group: str | None


class DashboardFiltersEcho(BaseModel):
    user_id: int
    since: date
    until: date
    muscle_groups: list[str]
    movement_patterns: list[str]
    target_only: bool


class BodyWeightEntry(BaseModel):
    date: date
    weight_kg: float


class DashboardResponse(BaseModel):
    days: list[date]
    kpsh_by_bucket: dict[str, list[int]]
    intensity_kg: list[float | None]
    kpsh_by_muscle: dict[str, int]
    kpsh_by_pattern: dict[str, int]
    total_workouts: int
    total_kpsh: int
    avg_intensity_kg: float | None
    filters: DashboardFiltersEcho


# ------------------------------------------------------------------ e1rm trend


class E1RMPointSchema(BaseModel):
    date: date
    canonical_name: str
    estimated_1rm_kg: float
    best_weight_kg: float
    best_reps: int


class E1RMTrendResponse(BaseModel):
    points: list[E1RMPointSchema]


# ------------------------------------------------------------------ weekly sets


class WeeklySetsBucketSchema(BaseModel):
    iso_week: str
    muscle_group: str
    hard_sets: int


class VolumeLandmarkSchema(BaseModel):
    mev: int
    mav: int
    mrv: int


class WeeklySetsResponse(BaseModel):
    buckets: list[WeeklySetsBucketSchema]
    landmarks: dict[str, VolumeLandmarkSchema]


# ------------------------------------------------------------------ tonnage trend


class TonnageWeekSchema(BaseModel):
    iso_week: str
    tonnage_kg: float


class TonnageTrendResponse(BaseModel):
    weeks: list[TonnageWeekSchema]


# ------------------------------------------------------------------ calendar


class CalendarDaySchema(BaseModel):
    date: date
    workout_count: int
    total_sets: int
    total_tonnage_kg: float


class CalendarResponse(BaseModel):
    days: list[CalendarDaySchema]


# ------------------------------------------------------------------ personal records


class PersonalRecordSchema(BaseModel):
    date: date
    canonical_name: str
    pr_type: str
    weight_kg: float
    reps: int
    estimated_1rm_kg: float
    previous_1rm_kg: float | None


class PRsResponse(BaseModel):
    records: list[PersonalRecordSchema]
