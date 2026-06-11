from __future__ import annotations

from datetime import UTC, date, datetime

from pwrbot.db.repo import ExerciseRow, SetRow, WorkoutRow
from pwrbot.metrics.e1rm_trend import E1RMPoint
from pwrbot.rules import flags
from pwrbot.rules.balance import BalanceMetrics
from pwrbot.rules.volume import VolumeMetrics


def _point(d: str, name: str, e1rm: float) -> E1RMPoint:
    return E1RMPoint(
        date=date.fromisoformat(d),
        canonical_name=name,
        estimated_1rm_kg=e1rm,
        best_weight_kg=e1rm * 0.9,
        best_reps=5,
    )


def _ts(d: str) -> int:
    return int(datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp())


def _workout(d: str, exercises: list[ExerciseRow] | None = None) -> WorkoutRow:
    ts = _ts(d)
    return WorkoutRow(
        id=0,
        user_id=1,
        performed_at=ts,
        logged_at=ts,
        source_text="",
        notes=None,
        exercises=exercises or [],
    )


def test_imbalance_flag_fires_outside_tolerance(yaml_config) -> None:
    b = BalanceMetrics(
        push_hard_sets=12,
        pull_hard_sets=5,
        squat_hard_sets=6,
        hinge_hard_sets=6,
        push_pull_ratio=12 / 5,   # 2.4, way above 1.3 ceiling
        squat_hinge_ratio=1.0,
    )
    result = flags.imbalance_flags(b, yaml_config.thresholds)
    kinds = [f["axis"] for f in result]
    assert "push_pull" in kinds
    assert "squat_hinge" not in kinds


def test_imbalance_flag_suppressed_when_smaller_side_below_min(yaml_config) -> None:
    """Single-session blip — smaller side (2 sets) below the 5-set minimum → no flag."""
    b = BalanceMetrics(
        push_hard_sets=10,
        pull_hard_sets=2,
        squat_hard_sets=6,
        hinge_hard_sets=6,
        push_pull_ratio=5.0,
        squat_hinge_ratio=1.0,
    )
    result = flags.imbalance_flags(b, yaml_config.thresholds)
    assert result == []


def test_recovery_flag_on_hard_set_cap(yaml_config) -> None:
    short = VolumeMetrics(
        hard_sets_by_pattern={"squat": 14, "hinge": 4, "push": 5, "pull": 5},
        total_tonnage_kg=1000,
    )
    result = flags.recovery_flags(
        short_window_metrics=short,
        previous_short_window_metrics=None,
        thresholds=yaml_config.thresholds,
    )
    squat_flag = next(f for f in result if f.get("pattern") == "squat")
    assert squat_flag["kind"] == "recovery_risk"
    assert squat_flag["hard_sets_7d"] == 14


def test_recovery_tonnage_spike_flag(yaml_config) -> None:
    short = VolumeMetrics(total_tonnage_kg=3000)
    prev = VolumeMetrics(total_tonnage_kg=1500)
    result = flags.recovery_flags(
        short_window_metrics=short,
        previous_short_window_metrics=prev,
        thresholds=yaml_config.thresholds,
    )
    spike = next(f for f in result if f.get("subtype") == "tonnage_spike")
    assert spike["ratio"] == 2.0


def test_recovery_no_tonnage_spike_when_below_ratio(yaml_config) -> None:
    short = VolumeMetrics(total_tonnage_kg=1800)
    prev = VolumeMetrics(total_tonnage_kg=1500)
    result = flags.recovery_flags(
        short_window_metrics=short,
        previous_short_window_metrics=prev,
        thresholds=yaml_config.thresholds,
    )
    assert all(f.get("subtype") != "tonnage_spike" for f in result)


# ------------------------------------------------------------------ stagnation


def test_stagnation_flag_fires_when_best_is_old(yaml_config) -> None:
    now_ts = _ts("2026-04-01T12:00:00")
    points = [
        _point("2026-03-01", "bench_press", 120.0),
        _point("2026-03-10", "bench_press", 118.0),
        _point("2026-03-25", "bench_press", 119.0),
    ]
    result = flags.stagnation_flags(points, now_ts=now_ts, thresholds=yaml_config.thresholds)
    assert len(result) == 1
    f = result[0]
    assert f["kind"] == "stagnation"
    assert f["exercise"] == "bench_press"
    assert f["best_e1rm_kg"] == 120.0
    assert f["days_since_best"] == 31


def test_stagnation_no_flag_when_recent_improvement(yaml_config) -> None:
    now_ts = _ts("2026-04-01T12:00:00")
    points = [
        _point("2026-03-01", "bench_press", 120.0),
        _point("2026-03-10", "bench_press", 118.0),
        _point("2026-03-25", "bench_press", 125.0),  # new best 7 days ago
    ]
    result = flags.stagnation_flags(points, now_ts=now_ts, thresholds=yaml_config.thresholds)
    assert result == []


def test_stagnation_no_flag_below_min_sessions(yaml_config) -> None:
    now_ts = _ts("2026-04-01T12:00:00")
    points = [
        _point("2026-03-01", "bench_press", 120.0),
        _point("2026-03-25", "bench_press", 110.0),
    ]
    result = flags.stagnation_flags(points, now_ts=now_ts, thresholds=yaml_config.thresholds)
    assert result == []


# ------------------------------------------------------------------ frequency


def test_frequency_drop_flag_fires(yaml_config) -> None:
    now_ts = _ts("2026-04-01T12:00:00")
    # 9 workouts over the prior 3 weeks (3/week), only 1 in the last 7 days
    prior = [_workout(f"2026-03-{day:02d}T10:00:00") for day in range(5, 23, 2)]
    current = [_workout("2026-03-30T10:00:00")]
    result = flags.frequency_drop_flags(
        prior + current, now_ts=now_ts, thresholds=yaml_config.thresholds
    )
    assert len(result) == 1
    assert result[0]["kind"] == "frequency_drop"
    assert result[0]["workouts_7d"] == 1
    assert result[0]["prior_weekly_avg"] == 3.0


def test_frequency_drop_no_flag_when_consistent(yaml_config) -> None:
    now_ts = _ts("2026-04-01T12:00:00")
    prior = [_workout(f"2026-03-{day:02d}T10:00:00") for day in range(5, 23, 2)]
    current = [
        _workout("2026-03-27T10:00:00"),
        _workout("2026-03-29T10:00:00"),
        _workout("2026-03-31T10:00:00"),
    ]
    result = flags.frequency_drop_flags(
        prior + current, now_ts=now_ts, thresholds=yaml_config.thresholds
    )
    assert result == []


def test_frequency_drop_no_flag_without_history(yaml_config) -> None:
    now_ts = _ts("2026-04-01T12:00:00")
    result = flags.frequency_drop_flags(
        [_workout("2026-03-31T10:00:00")], now_ts=now_ts, thresholds=yaml_config.thresholds
    )
    assert result == []


# ------------------------------------------------------------------ neglected pattern


def test_neglected_pattern_flag_fires(yaml_config) -> None:
    recent = VolumeMetrics(working_sets_by_pattern={"push": 5})
    prior = VolumeMetrics(working_sets_by_pattern={"push": 6, "squat": 4})
    result = flags.neglected_pattern_flags(
        recent_metrics=recent, prior_metrics=prior, thresholds=yaml_config.thresholds
    )
    assert len(result) == 1
    assert result[0]["kind"] == "neglected_pattern"
    assert result[0]["pattern"] == "squat"
    assert result[0]["prior_working_sets"] == 4


def test_neglected_pattern_ignores_accessory(yaml_config) -> None:
    recent = VolumeMetrics(working_sets_by_pattern={})
    prior = VolumeMetrics(working_sets_by_pattern={"accessory": 8})
    result = flags.neglected_pattern_flags(
        recent_metrics=recent, prior_metrics=prior, thresholds=yaml_config.thresholds
    )
    assert result == []


# ------------------------------------------------------------------ rep monotony


def _workout_with_sets(d: str, reps: int, n_sets: int) -> WorkoutRow:
    sets = [
        SetRow(reps=reps, weight_g=100_000, rpe=None, is_warmup=False, set_index=i)
        for i in range(1, n_sets + 1)
    ]
    ex = ExerciseRow(
        position=1,
        raw_name="присед",
        canonical_name="back_squat",
        movement_pattern="squat",
        sets=sets,
    )
    return _workout(d, [ex])


def test_rep_monotony_flag_fires(yaml_config) -> None:
    workouts = [
        _workout_with_sets("2026-03-10T10:00:00", reps=5, n_sets=12),
        _workout_with_sets("2026-03-20T10:00:00", reps=5, n_sets=12),
    ]
    result = flags.rep_monotony_flags(workouts, thresholds=yaml_config.thresholds)
    assert len(result) == 1
    assert result[0]["kind"] == "rep_monotony"
    assert result[0]["rep_range"] == "4-6"
    assert result[0]["share"] == 1.0


def test_rep_monotony_no_flag_when_mixed(yaml_config) -> None:
    workouts = [
        _workout_with_sets("2026-03-10T10:00:00", reps=5, n_sets=12),
        _workout_with_sets("2026-03-20T10:00:00", reps=10, n_sets=12),
    ]
    result = flags.rep_monotony_flags(workouts, thresholds=yaml_config.thresholds)
    assert result == []


def test_rep_monotony_no_flag_below_min_sets(yaml_config) -> None:
    workouts = [_workout_with_sets("2026-03-10T10:00:00", reps=5, n_sets=10)]
    result = flags.rep_monotony_flags(workouts, thresholds=yaml_config.thresholds)
    assert result == []
