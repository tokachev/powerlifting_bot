"""Training frequency per muscle group per ISO week — pure function."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime

from pwrbot.db.repo import WorkoutRow
from pwrbot.domain.catalog import Catalog
from pwrbot.metrics.util import iso_week_label


@dataclass(slots=True)
class FrequencyCell:
    iso_week: str
    muscle_group: str
    sessions: int


def compute_frequency(
    workouts: list[WorkoutRow],
    catalog: Catalog,
) -> list[FrequencyCell]:
    """Count distinct workout days per muscle group per ISO week."""
    # (iso_week, muscle_group) -> set of dates
    day_sets: dict[tuple[str, str], set[date]] = defaultdict(set)

    for w in workouts:
        d = datetime.fromtimestamp(w.performed_at, tz=UTC).date()
        week = iso_week_label(d)
        for ex in w.exercises:
            if ex.canonical_name is None:
                continue
            entry = catalog.by_canonical(ex.canonical_name)
            if entry is None or entry.muscle_group is None:
                continue
            day_sets[(week, entry.muscle_group)].add(d)

    result = [
        FrequencyCell(iso_week=week, muscle_group=mg, sessions=len(dates))
        for (week, mg), dates in day_sets.items()
    ]
    result.sort(key=lambda x: (x.iso_week, x.muscle_group))
    return result
