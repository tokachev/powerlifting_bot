"""PR detection — pure functions, no DB, no clock.

Given a workout's exercises+sets and the user's previous all-time bests,
detect which sets constitute new personal records.
"""

from __future__ import annotations

from dataclasses import dataclass

from pwrbot.db.repo import ExerciseRow
from pwrbot.rules.one_rm import estimate_1rm


@dataclass(slots=True)
class DetectedPR:
    canonical_name: str
    pr_type: str  # 'e1rm'
    weight_kg: float
    reps: int
    estimated_1rm_kg: float
    previous_1rm_kg: float | None  # None if first ever record


def detect_e1rm_prs(
    exercises: list[ExerciseRow],
    previous_bests: dict[str, float],
    max_reps: int = 12,
) -> list[DetectedPR]:
    """Scan exercises for sets whose e1RM exceeds the previous all-time best.

    Returns one DetectedPR per exercise (the best new e1RM for that exercise),
    only if it exceeds the previous best.  If no previous best exists, any valid
    set is a PR (first-ever record).

    Args:
        exercises: exercises from the current workout.
        previous_bests: canonical_name -> best e1RM in kg (from DB).
        max_reps: ignore sets with more reps (formula unreliable).
    """
    # best new e1RM per exercise in this workout
    best_per_exercise: dict[str, tuple[float, float, int]] = {}  # name -> (e1rm, weight, reps)

    for ex in exercises:
        if ex.canonical_name is None:
            continue
        for s in ex.sets:
            if s.is_warmup:
                continue
            if s.reps < 1 or s.reps > max_reps:
                continue
            kg = s.weight_g / 1000.0
            if kg <= 0:
                continue
            e1rm = estimate_1rm(kg, s.reps)
            cur = best_per_exercise.get(ex.canonical_name)
            if cur is None or e1rm > cur[0]:
                best_per_exercise[ex.canonical_name] = (e1rm, kg, s.reps)

    results: list[DetectedPR] = []
    for name, (e1rm, weight, reps) in best_per_exercise.items():
        prev = previous_bests.get(name)
        if prev is not None and e1rm <= prev:
            continue
        results.append(
            DetectedPR(
                canonical_name=name,
                pr_type="e1rm",
                weight_kg=weight,
                reps=reps,
                estimated_1rm_kg=e1rm,
                previous_1rm_kg=prev,
            )
        )

    return results
