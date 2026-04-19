"""Unit tests for 1RM / nRM estimation formulas and best-set finder."""

from __future__ import annotations

from pwrbot.db.repo import ExerciseRow, SetRow, WorkoutRow
from pwrbot.rules.one_rm import (
    brzycki_1rm,
    brzycki_nrm,
    compute_1rm_estimates,
    epley_1rm,
    epley_nrm,
    estimate_1rm,
    estimate_nrm,
    find_best_set,
)


def _set(reps: int, kg: float, rpe: float | None = None, warmup: bool = False, idx: int = 1) -> SetRow:
    return SetRow(
        reps=reps, weight_g=int(kg * 1000), rpe=rpe, is_warmup=warmup, set_index=idx,
    )


def _workout(performed_at: int, exercises: list[ExerciseRow]) -> WorkoutRow:
    return WorkoutRow(
        id=1, user_id=1, performed_at=performed_at, logged_at=performed_at,
        source_text="", notes=None, exercises=exercises,
    )


def _ex(name: str, pattern: str, sets: list[SetRow]) -> ExerciseRow:
    return ExerciseRow(
        position=1, raw_name=name, canonical_name=name, movement_pattern=pattern, sets=sets,
    )


# ------------------------------------------------------------------ formulas


def test_epley_single():
    assert epley_1rm(100.0, 1) == 100.0


def test_epley_5reps():
    # 100 * (1 + 5/30) = 116.666...
    assert abs(epley_1rm(100.0, 5) - 116.667) < 0.01


def test_epley_10reps():
    # 80 * (1 + 10/30) = 106.666...
    assert abs(epley_1rm(80.0, 10) - 106.667) < 0.01


def test_brzycki_single():
    assert brzycki_1rm(140.0, 1) == 140.0


def test_brzycki_3reps():
    # 140 * 36 / (37 - 3) = 140 * 36 / 34 = 148.235...
    assert abs(brzycki_1rm(140.0, 3) - 148.235) < 0.01


def test_brzycki_5reps():
    # 100 * 36 / (37 - 5) = 100 * 36 / 32 = 112.5
    assert brzycki_1rm(100.0, 5) == 112.5


def test_brzycki_high_reps_guard():
    # reps >= 37 → inf
    assert brzycki_1rm(100.0, 37) == float("inf")


def test_estimate_1rm_uses_brzycki_low_reps():
    # reps=5 should use Brzycki
    result = estimate_1rm(100.0, 5)
    expected = round(brzycki_1rm(100.0, 5), 1)
    assert result == expected


def test_estimate_1rm_uses_epley_high_reps():
    # reps=8 should use Epley
    result = estimate_1rm(80.0, 8)
    expected = round(epley_1rm(80.0, 8), 1)
    assert result == expected


def test_estimate_1rm_reps_1():
    assert estimate_1rm(150.0, 1) == 150.0


def test_estimate_1rm_reps_0():
    assert estimate_1rm(100.0, 0) == 0.0


def test_estimate_nrm_reps_1():
    assert estimate_nrm(150.0, 1) == 150.0


def test_estimate_nrm_uses_brzycki_inverse_low_reps():
    # reps=5, Brzycki inverse: 150 * (37-5)/36 = 150 * 32/36 = 133.33
    result = estimate_nrm(150.0, 5)
    expected = round(brzycki_nrm(150.0, 5), 1)
    assert result == expected
    assert abs(result - 133.3) < 0.1


def test_estimate_nrm_uses_epley_inverse_high_reps():
    # reps=8, Epley inverse: 150 * 30 / 38
    result = estimate_nrm(150.0, 8)
    expected = round(epley_nrm(150.0, 8), 1)
    assert result == expected


def test_estimate_nrm_boundary_r6_r7():
    # R=6 uses Brzycki, R=7 uses Epley — values should be close but computed by different formulas
    r6 = estimate_nrm(200.0, 6)
    r7 = estimate_nrm(200.0, 7)
    assert r6 == round(brzycki_nrm(200.0, 6), 1)
    assert r7 == round(epley_nrm(200.0, 7), 1)
    assert r6 > r7  # more reps → lighter


def test_estimate_nrm_symmetric_with_estimate_1rm():
    """200kg x 3 reps → 1RM. Reversing with estimate_nrm for 3 reps must return 200."""
    one_rm = estimate_1rm(200.0, 3)
    assert estimate_nrm(one_rm, 3) == 200.0


def test_estimate_nrm_monotonic_decreasing():
    one_rm = 200.0
    vals = [estimate_nrm(one_rm, r) for r in (1, 2, 3, 5, 8, 10)]
    assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))


def test_estimate_nrm_clamped():
    # Extreme reps won't go below 0
    result = estimate_nrm(50.0, 1000)
    assert result >= 0.0


# ------------------------------------------------------------------ find_best_set


def test_find_best_set_picks_highest_estimated():
    """Two sets, different weight/reps — pick the one with higher estimated 1RM."""
    history = [
        _workout(1000, [
            _ex("back_squat", "squat", [
                _set(5, 100),   # est = 100*36/32 = 112.5
                _set(3, 110),   # est = 110*36/34 ≈ 116.5
            ]),
        ]),
    ]
    best = find_best_set(history, "back_squat")
    assert best is not None
    weight, reps = best
    assert weight == 110.0
    assert reps == 3


def test_find_best_set_across_workouts():
    """Best set can come from a different workout."""
    history = [
        _workout(1000, [_ex("bench_press", "push", [_set(5, 80)])]),
        _workout(2000, [_ex("bench_press", "push", [_set(3, 100)])]),
    ]
    best = find_best_set(history, "bench_press")
    assert best is not None
    weight, reps = best
    assert weight == 100.0
    assert reps == 3


def test_find_best_set_skips_warmup():
    history = [
        _workout(1000, [
            _ex("back_squat", "squat", [
                _set(5, 140, warmup=True),
                _set(5, 100),
            ]),
        ]),
    ]
    best = find_best_set(history, "back_squat")
    assert best is not None
    assert best == (100.0, 5)


def test_find_best_set_skips_high_reps():
    """Sets with reps > max_reps are excluded."""
    history = [
        _workout(1000, [
            _ex("bench_press", "push", [
                _set(15, 80),   # reps > 12 → skip
                _set(5, 60),    # valid
            ]),
        ]),
    ]
    best = find_best_set(history, "bench_press")
    assert best is not None
    assert best == (60.0, 5)


def test_find_best_set_no_data():
    assert find_best_set([], "back_squat") is None


def test_find_best_set_no_matching_exercise():
    history = [
        _workout(1000, [_ex("deadlift", "hinge", [_set(3, 180)])]),
    ]
    assert find_best_set(history, "back_squat") is None


def test_find_best_set_skips_zero_weight():
    history = [
        _workout(1000, [_ex("back_squat", "squat", [_set(10, 0)])]),
    ]
    assert find_best_set(history, "back_squat") is None


# ------------------------------------------------------------------ compute_1rm_estimates


def test_compute_1rm_estimates_basic():
    history = [
        _workout(1000, [
            _ex("back_squat", "squat", [_set(5, 140)]),
            _ex("bench_press", "push", [_set(3, 100)]),
        ]),
    ]
    results = compute_1rm_estimates(
        history,
        [("back_squat", "squat"), ("bench_press", "bench")],
    )
    assert len(results) == 2
    squat = results[0]
    assert squat.canonical_name == "back_squat"
    assert squat.target_group == "squat"
    assert squat.best_set_weight_kg == 140.0
    assert squat.best_set_reps == 5
    assert squat.estimated_1rm_kg == estimate_1rm(140.0, 5)

    bench = results[1]
    assert bench.canonical_name == "bench_press"
    assert bench.target_group == "bench"


def test_compute_1rm_estimates_deduplicates():
    history = [
        _workout(1000, [_ex("back_squat", "squat", [_set(5, 100)])]),
    ]
    results = compute_1rm_estimates(
        history,
        [("back_squat", "squat"), ("back_squat", "squat")],
    )
    assert len(results) == 1


def test_compute_1rm_estimates_no_data():
    results = compute_1rm_estimates([], [("back_squat", "squat")])
    assert results == []
