"""Weekly tonnage trend — pure function, no DB, no clock."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from pwrbot.db.repo import WorkoutRow
from pwrbot.metrics.util import iso_week_label


@dataclass(slots=True)
class TonnageWeek:
    iso_week: str
    tonnage_kg: float


def compute_tonnage_trend(workouts: list[WorkoutRow]) -> list[TonnageWeek]:
    """Aggregate weekly tonnage (sum of reps * weight for non-warmup sets)."""
    by_week: dict[str, float] = defaultdict(float)

    for w in workouts:
        d = datetime.fromtimestamp(w.performed_at, tz=UTC).date()
        week = iso_week_label(d)
        for ex in w.exercises:
            for s in ex.sets:
                if s.is_warmup or s.reps <= 0:
                    continue
                kg = s.weight_g / 1000.0
                by_week[week] += s.reps * kg

    result = [
        TonnageWeek(iso_week=w, tonnage_kg=round(t, 2))
        for w, t in by_week.items()
    ]
    result.sort(key=lambda x: x.iso_week)
    return result
