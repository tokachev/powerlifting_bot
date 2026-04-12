"""1RM / nRM estimation from workout history.

Pure deterministic functions — no DB, no clock, no LLM.
Weight inputs from repo DTOs are in grams; outputs are human-friendly kg.
"""

from __future__ import annotations

from dataclasses import dataclass

from pwrbot.db.repo import WorkoutRow


@dataclass(slots=True)
class OneRMEstimate:
    canonical_name: str
    target_group: str | None
    best_set_weight_kg: float
    best_set_reps: int
    estimated_1rm_kg: float


def epley_1rm(weight_kg: float, reps: int) -> float:
    """Epley formula: w * (1 + reps/30). Identity for reps=1."""
    if reps <= 1:
        return weight_kg
    return weight_kg * (1 + reps / 30)


def brzycki_1rm(weight_kg: float, reps: int) -> float:
    """Brzycki formula: w * 36 / (37 - reps). Identity for reps=1."""
    if reps <= 1:
        return weight_kg
    denom = 37 - reps
    if denom <= 0:
        return float("inf")
    return weight_kg * 36 / denom


def estimate_1rm(weight_kg: float, reps: int) -> float:
    """Estimate 1RM: Brzycki for reps 1-6, Epley for 7+."""
    if reps <= 0:
        return 0.0
    if reps <= 6:
        return round(brzycki_1rm(weight_kg, reps), 1)
    return round(epley_1rm(weight_kg, reps), 1)


def estimate_nrm(one_rm_kg: float, reps: int) -> float:
    """Estimate nRM from a known 1RM using Epley inverse: 1RM * 30 / (30 + reps)."""
    if reps <= 1:
        return round(one_rm_kg, 1)
    result = one_rm_kg * 30 / (30 + reps)
    return round(max(result, 0.0), 1)


def find_best_set(
    history: list[WorkoutRow],
    canonical_name: str,
    max_reps: int = 12,
) -> tuple[float, int] | None:
    """Find the non-warmup set that yields the highest estimated 1RM.

    Returns ``(weight_kg, reps)`` or ``None`` if no qualifying sets exist.
    Only considers sets with 1 <= reps <= max_reps (formulas are unreliable above ~12).
    """
    best_est: float = 0.0
    best_pair: tuple[float, int] | None = None

    for w in history:
        for ex in w.exercises:
            if ex.canonical_name != canonical_name:
                continue
            for s in ex.sets:
                if s.is_warmup:
                    continue
                if s.reps < 1 or s.reps > max_reps:
                    continue
                kg = s.weight_g / 1000.0
                if kg <= 0:
                    continue
                est = estimate_1rm(kg, s.reps)
                if est > best_est:
                    best_est = est
                    best_pair = (kg, s.reps)

    return best_pair


def compute_1rm_estimates(
    history: list[WorkoutRow],
    exercises: list[tuple[str, str | None]],
) -> list[OneRMEstimate]:
    """Compute 1RM estimates for a list of (canonical_name, target_group) pairs.

    Deduplicates by canonical_name (only the first occurrence is kept).
    """
    seen: set[str] = set()
    results: list[OneRMEstimate] = []

    for canonical_name, target_group in exercises:
        if canonical_name in seen:
            continue
        seen.add(canonical_name)

        best = find_best_set(history, canonical_name)
        if best is None:
            continue

        weight_kg, reps = best
        results.append(
            OneRMEstimate(
                canonical_name=canonical_name,
                target_group=target_group,
                best_set_weight_kg=weight_kg,
                best_set_reps=reps,
                estimated_1rm_kg=estimate_1rm(weight_kg, reps),
            )
        )

    return results
