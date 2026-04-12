"""Unit tests for weekly hard-set counts per muscle group."""

from pwrbot.config import (
    BalanceThresholds,
    HardSetThresholds,
    RecoveryThresholds,
    Thresholds,
    WarmupThresholds,
)
from pwrbot.db.repo import ExerciseRow, SetRow, WorkoutRow
from pwrbot.domain.catalog import Catalog, CatalogEntry
from pwrbot.metrics.weekly_sets import compute_weekly_sets


def _make_thresholds():
    return Thresholds(
        hard_set=HardSetThresholds(min_rpe=7.0, intensity_fraction=0.75),
        balance=BalanceThresholds(
            push_pull_target=1.0, squat_hinge_target=1.0,
            tolerance=0.30, min_hard_sets_for_flag=5,
        ),
        recovery=RecoveryThresholds(
            max_hard_sets_7d={"squat": 12, "hinge": 10, "push": 16, "pull": 18},
            tonnage_spike_ratio=1.5,
        ),
        warmup=WarmupThresholds(max_fraction_of_working_weight=0.60),
    )


def _make_catalog():
    entries = [
        CatalogEntry(
            canonical_name="back_squat",
            movement_pattern="squat",
            aliases=("присед",),
            target_group="squat",
            muscle_group="legs",
        ),
        CatalogEntry(
            canonical_name="bench_press",
            movement_pattern="push",
            aliases=("жим лёжа",),
            target_group="bench",
            muscle_group="chest",
        ),
    ]
    return Catalog(entries)


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


# Monday 2026-03-02 00:00 UTC
TS_MON = 1_772_409_600


def test_basic_counting():
    workouts = [
        _w(TS_MON, [
            _ex("back_squat", [
                _s(5, 100_000, rpe=8.0, idx=0),
                _s(5, 100_000, rpe=8.0, idx=1),
                _s(5, 100_000, rpe=8.0, idx=2),
            ]),
        ]),
    ]
    catalog = _make_catalog()
    thresholds = _make_thresholds()
    buckets = compute_weekly_sets(workouts, catalog, thresholds)
    assert len(buckets) == 1
    assert buckets[0].muscle_group == "legs"
    assert buckets[0].hard_sets == 3


def test_warmup_excluded():
    workouts = [
        _w(TS_MON, [
            _ex("back_squat", [
                _s(5, 60_000, is_warmup=True, idx=0),
                _s(5, 100_000, rpe=8.0, idx=1),
            ]),
        ]),
    ]
    buckets = compute_weekly_sets(workouts, _make_catalog(), _make_thresholds())
    assert buckets[0].hard_sets == 1


def test_multiple_muscle_groups():
    workouts = [
        _w(TS_MON, [
            _ex("back_squat", [_s(5, 100_000, rpe=8.0)], position=0),
            _ex("bench_press", [_s(5, 80_000, rpe=8.0)], position=1),
        ]),
    ]
    buckets = compute_weekly_sets(workouts, _make_catalog(), _make_thresholds())
    assert len(buckets) == 2
    groups = {b.muscle_group: b.hard_sets for b in buckets}
    assert groups["legs"] == 1
    assert groups["chest"] == 1


def test_no_canonical_name_skipped():
    workouts = [_w(TS_MON, [_ex(None, [_s(5, 100_000, rpe=8.0)])])]
    buckets = compute_weekly_sets(workouts, _make_catalog(), _make_thresholds())
    assert buckets == []


def test_empty_workouts():
    assert compute_weekly_sets([], _make_catalog(), _make_thresholds()) == []
