"""E1RM trend computation — pure function, no DB, no clock."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from pwrbot.db.repo import WorkoutRow
from pwrbot.rules.one_rm import estimate_1rm


@dataclass(slots=True)
class E1RMPoint:
    date: date
    canonical_name: str
    estimated_1rm_kg: float
    best_weight_kg: float
    best_reps: int


def compute_e1rm_trend(
    workouts: list[WorkoutRow],
    canonical_names: list[str],
    max_reps: int = 12,
) -> list[E1RMPoint]:
    """Compute the best e1RM per exercise per day from the given workouts.

    Returns one E1RMPoint per (date, exercise) pair where data exists,
    sorted by date ascending.
    """
    # (date, canonical) -> (e1rm, weight_kg, reps)
    best: dict[tuple[date, str], tuple[float, float, int]] = {}

    for w in workouts:
        d = datetime.fromtimestamp(w.performed_at, tz=UTC).date()
        for ex in w.exercises:
            if ex.canonical_name is None or ex.canonical_name not in canonical_names:
                continue
            for s in ex.sets:
                if s.is_warmup or s.reps < 1 or s.reps > max_reps:
                    continue
                kg = s.weight_g / 1000.0
                if kg <= 0:
                    continue
                e1rm = estimate_1rm(kg, s.reps)
                key = (d, ex.canonical_name)
                cur = best.get(key)
                if cur is None or e1rm > cur[0]:
                    best[key] = (e1rm, kg, s.reps)

    points = [
        E1RMPoint(
            date=d,
            canonical_name=name,
            estimated_1rm_kg=e1rm,
            best_weight_kg=weight,
            best_reps=reps,
        )
        for (d, name), (e1rm, weight, reps) in best.items()
    ]
    points.sort(key=lambda p: (p.date, p.canonical_name))
    return points
