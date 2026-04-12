"""Unit tests for calendar heatmap aggregation."""

from datetime import date

from pwrbot.db.repo import ExerciseRow, SetRow, WorkoutRow
from pwrbot.metrics.calendar import compute_calendar


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


def _s(reps, weight_g, is_warmup=False, idx=0):
    return SetRow(reps=reps, weight_g=weight_g, rpe=None, is_warmup=is_warmup, set_index=idx)


# 2026-03-02 00:00 UTC
TS_MAR02 = 1_772_409_600


def test_single_workout():
    workouts = [_w(TS_MAR02, [_ex("back_squat", [_s(5, 100_000)])])]
    days = compute_calendar(workouts)
    assert len(days) == 1
    d = days[0]
    assert d.date == date(2026, 3, 2)
    assert d.workout_count == 1
    assert d.total_sets == 1
    assert d.total_tonnage_kg == 500.0


def test_warmup_excluded_from_sets_and_tonnage():
    workouts = [
        _w(TS_MAR02, [
            _ex("back_squat", [
                _s(5, 60_000, is_warmup=True, idx=0),
                _s(5, 100_000, idx=1),
            ]),
        ]),
    ]
    days = compute_calendar(workouts)
    assert days[0].total_sets == 1
    assert days[0].total_tonnage_kg == 500.0


def test_two_workouts_same_day():
    workouts = [
        _w(TS_MAR02, [_ex("back_squat", [_s(5, 100_000)])], wid=1),
        _w(TS_MAR02 + 3600, [_ex("bench_press", [_s(5, 80_000)])], wid=2),
    ]
    days = compute_calendar(workouts)
    assert len(days) == 1
    assert days[0].workout_count == 2
    assert days[0].total_sets == 2


def test_multiple_days():
    ts_next = TS_MAR02 + 86_400
    workouts = [
        _w(TS_MAR02, [_ex("back_squat", [_s(5, 100_000)])], wid=1),
        _w(ts_next, [_ex("bench_press", [_s(5, 80_000)])], wid=2),
    ]
    days = compute_calendar(workouts)
    assert len(days) == 2
    assert days[0].date < days[1].date


def test_empty():
    assert compute_calendar([]) == []
