"""Rep distribution across working sets — pure function."""

from __future__ import annotations

from dataclasses import dataclass

from pwrbot.db.repo import WorkoutRow

BUCKETS = [
    ("1-3", 1, 3),
    ("4-6", 4, 6),
    ("7-9", 7, 9),
    ("10-12", 10, 12),
    ("13+", 13, 999),
]


@dataclass(slots=True)
class RepBucket:
    rep_range: str
    set_count: int
    rep_count: int


def compute_rep_distribution(
    workouts: list[WorkoutRow],
    canonical_name: str | None = None,
) -> list[RepBucket]:
    """Count working sets and reps by rep-range bucket.

    If ``canonical_name`` is given, only count sets for that exercise.
    Warmup sets are excluded.
    """
    counts: dict[str, list[int]] = {label: [0, 0] for label, _, _ in BUCKETS}

    for w in workouts:
        for ex in w.exercises:
            if canonical_name and ex.canonical_name != canonical_name:
                continue
            for s in ex.sets:
                if s.is_warmup or s.reps <= 0:
                    continue
                for label, lo, hi in BUCKETS:
                    if lo <= s.reps <= hi:
                        counts[label][0] += 1
                        counts[label][1] += s.reps
                        break

    return [
        RepBucket(rep_range=label, set_count=c[0], rep_count=c[1])
        for label, _, _ in BUCKETS
        for c in [counts[label]]
    ]
