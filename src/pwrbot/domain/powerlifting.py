"""Pydantic models for powerlifting-specific entities.

Kg at the domain boundary, grams in the repo layer.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Lift = Literal["squat", "bench", "deadlift"]
AttemptStatus = Literal["planned", "made", "missed"]
Severity = Literal["good", "warn", "crit"]
TechniqueSource = Literal["user", "llm", "video"]
PhaseName = Literal["hypertrophy", "strength", "peaking", "deload"]


class MeetAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lift: Lift
    attempt_no: int = Field(ge=1, le=3)
    weight_kg: float = Field(ge=0, le=600)
    status: AttemptStatus = "planned"


class Meet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    meet_date: date
    name: str = Field(min_length=1)
    category: str | None = None
    federation: str | None = None
    bodyweight_kg: float | None = Field(default=None, ge=30, le=250)
    squat_kg: float = Field(ge=0, le=600)
    bench_kg: float = Field(ge=0, le=400)
    deadlift_kg: float = Field(ge=0, le=600)
    total_kg: float = Field(ge=0, le=1500)
    wilks: float | None = None
    dots: float | None = None
    ipf_gl: float | None = None
    place: int | None = Field(default=None, ge=1)
    is_gym_meet: bool = False
    notes: str | None = None
    attempts: list[MeetAttempt] = Field(default_factory=list)


class NextMeet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meet_date: date
    name: str
    category: str | None = None
    federation: str | None = None
    target_squat_kg: float = Field(ge=0, le=600)
    target_bench_kg: float = Field(ge=0, le=400)
    target_deadlift_kg: float = Field(ge=0, le=600)
    # attempts by lift, each list has at most 3 entries (1st/2nd/3rd attempts)
    attempts: dict[Lift, list[float]] = Field(
        default_factory=lambda: {"squat": [], "bench": [], "deadlift": []}
    )


class RecoveryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recorded_date: date
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    hrv_ms: float | None = Field(default=None, ge=0, le=300)
    rhr_bpm: int | None = Field(default=None, ge=20, le=200)
    recovery_pct: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = None


class Niggle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    recorded_date: date
    body_area: str
    severity: Severity
    note: str | None = None
    resolved: bool = False


class TechniqueNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    canonical_name: str
    recorded_date: date
    note_text: str
    source: TechniqueSource = "user"


class TrainingPhase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    phase_name: str
    start_date: date
    end_date: date
    color_hex: str | None = None
    notes: str | None = None
