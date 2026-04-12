"""Per-exercise detail: all sessions for a single exercise — pure function."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from pwrbot.db.repo import WorkoutRow
from pwrbot.rules.one_rm import estimate_1rm


@dataclass(slots=True)
class SetDetail:
    reps: int
    weight_kg: float
    rpe: float | None
    is_warmup: bool
    estimated_1rm_kg: float | None


@dataclass(slots=True)
class ExerciseSession:
    date: date
    best_e1rm_kg: float
    total_volume_kg: float
    sets: list[SetDetail] = field(default_factory=list)


def compute_per_exercise(
    workouts: list[WorkoutRow],
    canonical_name: str,
    max_reps: int = 12,
) -> list[ExerciseSession]:
    """Extract all sessions for a single exercise, sorted by date."""
    by_date: dict[date, ExerciseSession] = {}

    for w in workouts:
        d = datetime.fromtimestamp(w.performed_at, tz=UTC).date()
        for ex in w.exercises:
            if ex.canonical_name != canonical_name:
                continue
            if d not in by_date:
                by_date[d] = ExerciseSession(date=d, best_e1rm_kg=0.0, total_volume_kg=0.0)
            session = by_date[d]

            for s in ex.sets:
                kg = s.weight_g / 1000.0
                e1rm: float | None = None
                if not s.is_warmup and 1 <= s.reps <= max_reps and kg > 0:
                    e1rm = estimate_1rm(kg, s.reps)
                    if e1rm > session.best_e1rm_kg:
                        session.best_e1rm_kg = e1rm
                if not s.is_warmup and s.reps > 0:
                    session.total_volume_kg += s.reps * kg
                session.sets.append(
                    SetDetail(
                        reps=s.reps,
                        weight_kg=kg,
                        rpe=s.rpe,
                        is_warmup=s.is_warmup,
                        estimated_1rm_kg=e1rm,
                    )
                )

    result = list(by_date.values())
    for s in result:
        s.total_volume_kg = round(s.total_volume_kg, 2)
    result.sort(key=lambda x: x.date)
    return result
