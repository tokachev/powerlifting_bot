"""Calendar heatmap aggregation — pure function, no DB, no clock."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime

from pwrbot.db.repo import WorkoutRow


@dataclass(slots=True)
class CalendarDay:
    date: date
    workout_count: int
    total_sets: int
    total_tonnage_kg: float


def compute_calendar(workouts: list[WorkoutRow]) -> list[CalendarDay]:
    """Aggregate per-day workout summary for calendar heatmap.

    Returns one CalendarDay per day that has data, sorted by date ascending.
    """
    by_day: dict[date, list[int, int, float]] = defaultdict(lambda: [0, 0, 0.0])

    for w in workouts:
        d = datetime.fromtimestamp(w.performed_at, tz=UTC).date()
        acc = by_day[d]
        acc[0] += 1  # workout_count
        for ex in w.exercises:
            for s in ex.sets:
                if s.is_warmup:
                    continue
                acc[1] += 1  # total_sets
                acc[2] += s.reps * (s.weight_g / 1000.0)  # tonnage

    result = [
        CalendarDay(
            date=d,
            workout_count=acc[0],
            total_sets=acc[1],
            total_tonnage_kg=round(acc[2], 2),
        )
        for d, acc in by_day.items()
    ]
    result.sort(key=lambda x: x.date)
    return result
