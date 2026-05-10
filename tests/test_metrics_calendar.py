"""Unit tests for calendar heatmap aggregation."""

from datetime import UTC, date, datetime

from pwrbot.db.repo import ExerciseRow, SetRow, WorkoutRow
from pwrbot.domain.catalog import Catalog, CatalogEntry
from pwrbot.metrics.calendar import compute_calendar
from pwrbot.metrics.powerlifting import compute_calendar_heatmap_16w


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


# ---- compute_calendar_heatmap_16w --------------------------------------------------

TODAY = date(2026, 5, 10)


def _ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


def _heatmap_catalog() -> Catalog:
    return Catalog([
        CatalogEntry(
            canonical_name="back_squat", movement_pattern="squat",
            aliases=("присед",), target_group="squat", muscle_group="legs",
            main_lift_coefficient=1.0,
        ),
        CatalogEntry(
            canonical_name="front_squat", movement_pattern="squat",
            aliases=("фронт",), target_group="squat", muscle_group="legs",
            main_lift_coefficient=0.85,
        ),
        CatalogEntry(
            canonical_name="bench_press", movement_pattern="push",
            aliases=("жим",), target_group="bench", muscle_group="chest",
            main_lift_coefficient=1.0,
        ),
        CatalogEntry(
            canonical_name="deadlift", movement_pattern="hinge",
            aliases=("становая",), target_group="deadlift", muscle_group="back",
            main_lift_coefficient=1.0,
        ),
        CatalogEntry(
            canonical_name="db_curl", movement_pattern="accessory",
            aliases=("сгибания",), muscle_group="arms",
        ),
    ])


def test_heatmap_returns_112_days_ending_today():
    cells = compute_calendar_heatmap_16w([], catalog=_heatmap_catalog(), today=TODAY)
    assert len(cells) == 112
    assert cells[-1].day == TODAY
    assert cells[0].day == date(2026, 1, 19)  # 111 days before 2026-05-10


def test_heatmap_empty_history():
    cells = compute_calendar_heatmap_16w([], catalog=_heatmap_catalog(), today=TODAY)
    for c in cells:
        assert c.intensity == 0
        assert c.tonnage_kg == 0.0
        assert c.max_squat_kg is None
        assert c.max_bench_kg is None
        assert c.max_deadlift_kg is None


def test_heatmap_primary_squat_sets_max_squat_only():
    workouts = [_w(_ts(TODAY), [_ex("back_squat", [_s(5, 200_000), _s(3, 220_000)])])]
    cells = compute_calendar_heatmap_16w(workouts, catalog=_heatmap_catalog(), today=TODAY)
    today_cell = cells[-1]
    assert today_cell.tonnage_kg == 5 * 200.0 + 3 * 220.0
    assert today_cell.max_squat_kg == 220.0
    assert today_cell.max_bench_kg is None
    assert today_cell.max_deadlift_kg is None
    assert today_cell.intensity == 4  # only one nonzero day → it is the peak


def test_heatmap_variant_excluded_from_max_but_counted_in_tonnage():
    workouts = [_w(_ts(TODAY), [_ex("front_squat", [_s(5, 150_000)])])]
    cells = compute_calendar_heatmap_16w(workouts, catalog=_heatmap_catalog(), today=TODAY)
    today_cell = cells[-1]
    assert today_cell.tonnage_kg == 5 * 150.0
    assert today_cell.max_squat_kg is None
    assert today_cell.max_bench_kg is None
    assert today_cell.max_deadlift_kg is None


def test_heatmap_mixed_day_only_primary_lift_in_max():
    workouts = [_w(_ts(TODAY), [
        _ex("bench_press", [_s(5, 120_000)], position=0),
        _ex("front_squat", [_s(5, 150_000)], position=1),
    ])]
    cells = compute_calendar_heatmap_16w(workouts, catalog=_heatmap_catalog(), today=TODAY)
    today_cell = cells[-1]
    assert today_cell.max_bench_kg == 120.0
    assert today_cell.max_squat_kg is None
    assert today_cell.max_deadlift_kg is None


def test_heatmap_warmup_excluded():
    workouts = [_w(_ts(TODAY), [_ex("back_squat", [
        _s(5, 100_000, is_warmup=True, idx=0),
        _s(3, 200_000, idx=1),
    ])])]
    cells = compute_calendar_heatmap_16w(workouts, catalog=_heatmap_catalog(), today=TODAY)
    today_cell = cells[-1]
    assert today_cell.tonnage_kg == 3 * 200.0
    assert today_cell.max_squat_kg == 200.0


def test_heatmap_intensity_buckets_relative_to_peak():
    # Four nonzero days with tonnages 1000, 3000, 6000, 9000. Peak = 9000.
    # ratios → 0.111, 0.333, 0.667, 1.0 → ceil(4*r) → 1, 2, 3, 4.
    days_back_and_reps = [
        (date(2026, 5, 4), 10),   # 10*100 = 1000  → bucket 1
        (date(2026, 5, 5), 30),   # 30*100 = 3000  → bucket 2
        (date(2026, 5, 6), 60),   # 60*100 = 6000  → bucket 3
        (date(2026, 5, 7), 90),   # 90*100 = 9000  → bucket 4 (peak)
    ]
    workouts = [
        _w(_ts(d), [_ex("back_squat", [_s(reps, 100_000)])], wid=i + 1)
        for i, (d, reps) in enumerate(days_back_and_reps)
    ]
    cells = compute_calendar_heatmap_16w(workouts, catalog=_heatmap_catalog(), today=TODAY)
    by_day = {c.day: c for c in cells}
    assert by_day[date(2026, 5, 4)].intensity == 1
    assert by_day[date(2026, 5, 5)].intensity == 2
    assert by_day[date(2026, 5, 6)].intensity == 3
    assert by_day[date(2026, 5, 7)].intensity == 4
    # all other days are 0
    assert by_day[TODAY].intensity == 0


def test_heatmap_outside_window_ignored():
    too_old = date(2026, 1, 18)  # 112 days before TODAY → excluded
    workouts = [_w(_ts(too_old), [_ex("back_squat", [_s(5, 200_000)])])]
    cells = compute_calendar_heatmap_16w(workouts, catalog=_heatmap_catalog(), today=TODAY)
    for c in cells:
        assert c.tonnage_kg == 0.0
        assert c.intensity == 0
        assert c.max_squat_kg is None
