"""Weekly hard-set counts per muscle group — pure function, no DB, no clock."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from pwrbot.config import Thresholds
from pwrbot.db.repo import WorkoutRow
from pwrbot.domain.catalog import Catalog
from pwrbot.metrics.util import iso_week_label
from pwrbot.rules.volume import is_hard_set, rolling_best_weight_kg


@dataclass(slots=True)
class WeeklySetsBucket:
    iso_week: str
    muscle_group: str
    hard_sets: int


def compute_weekly_sets(
    workouts: list[WorkoutRow],
    catalog: Catalog,
    thresholds: Thresholds,
    history_for_intensity: list[WorkoutRow] | None = None,
) -> list[WeeklySetsBucket]:
    """Aggregate hard sets per muscle group per ISO week.

    Week boundaries are ISO weeks (Mon-Sun) in UTC.
    ``history_for_intensity`` is used only for rolling-best weights when RPE
    is missing. Pass the full 28-day history here.
    """
    history = history_for_intensity if history_for_intensity is not None else workouts

    # (iso_week, muscle_group) -> hard_sets
    counts: dict[tuple[str, str], int] = defaultdict(int)

    for w in workouts:
        d = datetime.fromtimestamp(w.performed_at, tz=UTC).date()
        week = iso_week_label(d)
        for ex in w.exercises:
            if ex.canonical_name is None:
                continue
            entry = catalog.by_canonical(ex.canonical_name)
            if entry is None or entry.muscle_group is None:
                continue
            mg = entry.muscle_group
            rb = rolling_best_weight_kg(history, ex.canonical_name)
            for s in ex.sets:
                if s.is_warmup:
                    continue
                kg = s.weight_g / 1000.0
                if is_hard_set(
                    reps=s.reps,
                    weight_kg=kg,
                    rpe=s.rpe,
                    thresholds=thresholds,
                    rolling_best_kg=rb,
                ):
                    counts[(week, mg)] += 1

    result = [
        WeeklySetsBucket(iso_week=week, muscle_group=mg, hard_sets=n)
        for (week, mg), n in counts.items()
    ]
    result.sort(key=lambda b: (b.iso_week, b.muscle_group))
    return result
