"""Pydantic models — the canonical in-memory representation of a workout.

The `WorkoutPayload.model_json_schema()` output is passed verbatim to Ollama
as the `format` parameter, so pydantic also defines the LLM output contract.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SetPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reps: int = Field(ge=0, le=100)
    weight_kg: float = Field(ge=0, le=500)
    rpe: float | None = Field(default=None, ge=0, le=10)
    is_warmup: bool = False


class ExercisePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_name: str = Field(min_length=1)
    canonical_name: str | None = None
    sets: list[SetPayload] = Field(min_length=1)


class WorkoutPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    performed_at: datetime | None = None
    notes: str | None = None
    exercises: list[ExercisePayload] = Field(min_length=1)
