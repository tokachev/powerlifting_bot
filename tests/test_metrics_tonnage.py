"""Unit tests for tonnage trend computation."""

from pwrbot.db.repo import ExerciseRow, SetRow, WorkoutRow
from pwrbot.metrics.tonnage_trend import compute_tonnage_trend


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


# Monday 2026-03-02 00:00 UTC
TS_MON = 1_772_409_600


def test_basic_tonnage():
    workouts = [
        _w(TS_MON, [_ex("back_squat", [_s(5, 100_000, idx=0), _s(5, 100_000, idx=1)])]),
    ]
    weeks = compute_tonnage_trend(workouts)
    assert len(weeks) == 1
    # 5*100 + 5*100 = 1000 kg
    assert weeks[0].tonnage_kg == 1000.0


def test_warmup_excluded():
    workouts = [
        _w(TS_MON, [
            _ex("back_squat", [
                _s(5, 60_000, is_warmup=True, idx=0),
                _s(5, 100_000, idx=1),
            ]),
        ]),
    ]
    weeks = compute_tonnage_trend(workouts)
    assert weeks[0].tonnage_kg == 500.0


def test_multiple_weeks():
    ts_next_week = TS_MON + 7 * 86_400
    workouts = [
        _w(TS_MON, [_ex("back_squat", [_s(5, 100_000)])], wid=1),
        _w(ts_next_week, [_ex("back_squat", [_s(5, 100_000)])], wid=2),
    ]
    weeks = compute_tonnage_trend(workouts)
    assert len(weeks) == 2


def test_empty():
    assert compute_tonnage_trend([]) == []
