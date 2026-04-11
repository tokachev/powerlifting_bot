"""Volume/tonnage/hard-sets computation over a list of WorkoutRow.

All inputs are repo DTOs (grams), all outputs are human-friendly kg/counts.
Pure functions — no DB, no clock, no LLM.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from pwrbot.config import Thresholds
from pwrbot.db.repo import WorkoutRow


@dataclass(slots=True)
class VolumeMetrics:
    total_working_sets: int = 0
    total_hard_sets: int = 0
    total_tonnage_kg: float = 0.0
    working_sets_by_pattern: dict[str, int] = field(default_factory=dict)
    hard_sets_by_pattern: dict[str, int] = field(default_factory=dict)
    tonnage_by_pattern_kg: dict[str, float] = field(default_factory=dict)


def _rolling_best_weight_kg(
    history: list[WorkoutRow], canonical_name: str | None
) -> float | None:
    """Return the maximum non-warmup weight seen for the given canonical across the history."""
    if canonical_name is None:
        return None
    best: float | None = None
    for w in history:
        for ex in w.exercises:
            if ex.canonical_name != canonical_name:
                continue
            for s in ex.sets:
                if s.is_warmup:
                    continue
                kg = s.weight_g / 1000.0
                if best is None or kg > best:
                    best = kg
    return best


def _is_hard_set(
    *,
    reps: int,
    weight_kg: float,
    rpe: float | None,
    thresholds: Thresholds,
    rolling_best_kg: float | None,
) -> bool:
    if reps <= 0:
        return False
    if rpe is not None:
        return rpe >= thresholds.hard_set.min_rpe
    # No RPE → use intensity fraction if we have a rolling best
    if rolling_best_kg is not None and rolling_best_kg > 0:
        return weight_kg >= rolling_best_kg * thresholds.hard_set.intensity_fraction
    # No history, no RPE → count every working set as hard (conservative for recovery flags)
    return True


def compute(
    workouts: list[WorkoutRow],
    thresholds: Thresholds,
    history_for_intensity: list[WorkoutRow] | None = None,
) -> VolumeMetrics:
    """Compute volume metrics for `workouts`. `history_for_intensity` is used ONLY
    to derive rolling-best weights when RPE is missing. Usually you pass the 28-day
    history here regardless of which window you're analyzing."""

    history = history_for_intensity if history_for_intensity is not None else workouts

    m = VolumeMetrics()
    working_by_pattern: dict[str, int] = defaultdict(int)
    hard_by_pattern: dict[str, int] = defaultdict(int)
    tonnage_by_pattern: dict[str, float] = defaultdict(float)

    for w in workouts:
        for ex in w.exercises:
            pattern = ex.movement_pattern or "unknown"
            rolling_best = _rolling_best_weight_kg(history, ex.canonical_name)
            for s in ex.sets:
                if s.is_warmup:
                    continue
                m.total_working_sets += 1
                working_by_pattern[pattern] += 1

                kg = s.weight_g / 1000.0
                tonnage = s.reps * kg
                m.total_tonnage_kg += tonnage
                tonnage_by_pattern[pattern] += tonnage

                if _is_hard_set(
                    reps=s.reps,
                    weight_kg=kg,
                    rpe=s.rpe,
                    thresholds=thresholds,
                    rolling_best_kg=rolling_best,
                ):
                    m.total_hard_sets += 1
                    hard_by_pattern[pattern] += 1

    m.working_sets_by_pattern = dict(working_by_pattern)
    m.hard_sets_by_pattern = dict(hard_by_pattern)
    m.tonnage_by_pattern_kg = {k: round(v, 2) for k, v in tonnage_by_pattern.items()}
    m.total_tonnage_kg = round(m.total_tonnage_kg, 2)
    return m
