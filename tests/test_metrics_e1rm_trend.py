"""Unit tests for e1RM trend computation."""

from datetime import date

from pwrbot.db.repo import ExerciseRow, SetRow, WorkoutRow
from pwrbot.metrics.e1rm_trend import compute_e1rm_trend
from pwrbot.rules.one_rm import estimate_1rm


def _w(performed_at_ts, exercises, wid=1):
    return WorkoutRow(
        id=wid, user_id=1, performed_at=performed_at_ts,
        logged_at=performed_at_ts, source_text="", notes=None,
        exercises=exercises,
    )


def _ex(canonical_name, sets, position=0):
    return ExerciseRow(
        position=position, raw_name=canonical_name or "raw",
        canonical_name=canonical_name, movement_pattern="squat", sets=sets,
    )


def _s(reps, weight_g, rpe=None, is_warmup=False, idx=0):
    return SetRow(reps=reps, weight_g=weight_g, rpe=rpe, is_warmup=is_warmup, set_index=idx)


# 2026-03-01 00:00 UTC
TS_MAR01 = 1_772_323_200
TS_MAR02 = TS_MAR01 + 86_400


def test_single_exercise_single_day():
    workouts = [_w(TS_MAR01, [_ex("back_squat", [_s(5, 100_000)])])]
    points = compute_e1rm_trend(workouts, ["back_squat"])
    assert len(points) == 1
    assert points[0].canonical_name == "back_squat"
    assert points[0].date == date(2026, 3, 1)
    assert points[0].estimated_1rm_kg == estimate_1rm(100.0, 5)
    assert points[0].best_weight_kg == 100.0
    assert points[0].best_reps == 5


def test_best_set_per_day():
    workouts = [
        _w(TS_MAR01, [
            _ex("back_squat", [
                _s(5, 100_000, idx=0),
                _s(3, 110_000, idx=1),  # higher e1RM
            ]),
        ]),
    ]
    points = compute_e1rm_trend(workouts, ["back_squat"])
    assert len(points) == 1
    assert points[0].best_weight_kg == 110.0


def test_multiple_days():
    workouts = [
        _w(TS_MAR01, [_ex("back_squat", [_s(5, 100_000)])], wid=1),
        _w(TS_MAR02, [_ex("back_squat", [_s(5, 105_000)])], wid=2),
    ]
    points = compute_e1rm_trend(workouts, ["back_squat"])
    assert len(points) == 2
    assert points[0].date < points[1].date


def test_multiple_exercises():
    workouts = [
        _w(TS_MAR01, [
            _ex("back_squat", [_s(5, 100_000)], position=0),
            _ex("bench_press", [_s(5, 70_000)], position=1),
        ]),
    ]
    points = compute_e1rm_trend(workouts, ["back_squat", "bench_press"])
    assert len(points) == 2
    names = {p.canonical_name for p in points}
    assert names == {"back_squat", "bench_press"}


def test_filters_to_requested_exercises():
    workouts = [
        _w(TS_MAR01, [
            _ex("back_squat", [_s(5, 100_000)], position=0),
            _ex("bench_press", [_s(5, 70_000)], position=1),
        ]),
    ]
    points = compute_e1rm_trend(workouts, ["back_squat"])
    assert len(points) == 1
    assert points[0].canonical_name == "back_squat"


def test_warmup_excluded():
    workouts = [_w(TS_MAR01, [_ex("back_squat", [_s(5, 200_000, is_warmup=True)])])]
    points = compute_e1rm_trend(workouts, ["back_squat"])
    assert points == []


def test_high_reps_excluded():
    workouts = [_w(TS_MAR01, [_ex("back_squat", [_s(20, 60_000)])])]
    points = compute_e1rm_trend(workouts, ["back_squat"])
    assert points == []


def test_empty_workouts():
    assert compute_e1rm_trend([], ["back_squat"]) == []
