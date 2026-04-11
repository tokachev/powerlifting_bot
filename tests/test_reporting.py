"""Unit tests for ReportingService.build_dashboard."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from pwrbot.db import repo
from pwrbot.db.repo import ExerciseRow, SetRow
from pwrbot.domain.catalog import load_catalog
from pwrbot.services.reporting import (
    BUCKETS,
    DashboardData,
    FilterSpec,
    build_dashboard,
)
from tests.conftest import REPO_ROOT


def _ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


def _eod(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC).timestamp())


async def _seed(
    conn,
    *,
    user_id: int,
    performed_at: int,
    exercises: list[ExerciseRow],
) -> int:
    return await repo.insert_workout(
        conn,
        user_id=user_id,
        performed_at=performed_at,
        source_text="test",
        exercises=exercises,
    )


def _ex(
    canonical_name: str,
    movement_pattern: str,
    sets: list[tuple[int, int, bool]],
    *,
    position: int = 0,
    raw_name: str | None = None,
) -> ExerciseRow:
    """Build an ExerciseRow from (reps, weight_kg, is_warmup) tuples."""
    return ExerciseRow(
        position=position,
        raw_name=raw_name or canonical_name,
        canonical_name=canonical_name,
        movement_pattern=movement_pattern,
        sets=[
            SetRow(
                reps=reps,
                weight_g=weight_kg * 1000,
                rpe=None,
                is_warmup=warmup,
                set_index=i,
            )
            for i, (reps, weight_kg, warmup) in enumerate(sets)
        ],
    )


async def test_empty_window_returns_zeros(conn) -> None:
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    today = date(2026, 4, 1)
    data = await build_dashboard(
        conn,
        user_id=uid,
        since_ts=_ts(today - timedelta(days=6)),
        until_ts=_eod(today),
        filter_spec=FilterSpec(),
        catalog=catalog,
    )
    assert isinstance(data, DashboardData)
    assert len(data.days) == 7
    assert all(sum(v) == 0 for v in data.kpsh_by_bucket.values())
    assert all(x is None for x in data.intensity_kg)
    assert data.total_workouts == 0
    assert data.total_kpsh == 0
    assert data.avg_intensity_kg is None
    # All buckets present even when empty
    assert set(data.kpsh_by_bucket.keys()) == set(BUCKETS)


async def test_one_day_squat_and_bench_buckets(conn) -> None:
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    today = date(2026, 4, 1)
    await _seed(
        conn,
        user_id=uid,
        performed_at=_ts(today) + 12 * 3600,
        exercises=[
            _ex("back_squat", "squat", [(5, 100, False), (5, 100, False)]),
            _ex("bench_press", "push", [(8, 80, False), (8, 80, False)], position=1),
        ],
    )
    data = await build_dashboard(
        conn,
        user_id=uid,
        since_ts=_ts(today - timedelta(days=2)),
        until_ts=_eod(today),
        filter_spec=FilterSpec(),
        catalog=catalog,
    )
    today_idx = data.days.index(today)
    assert data.kpsh_by_bucket["squat"][today_idx] == 10
    assert data.kpsh_by_bucket["bench"][today_idx] == 16
    assert data.kpsh_by_bucket["deadlift"][today_idx] == 0
    assert data.kpsh_by_bucket["other"][today_idx] == 0
    assert data.total_kpsh == 26
    assert data.total_workouts == 1
    # Other days are zero / None
    for i, d in enumerate(data.days):
        if d != today:
            assert data.kpsh_by_bucket["squat"][i] == 0
            assert data.intensity_kg[i] is None


async def test_warmup_sets_excluded(conn) -> None:
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    today = date(2026, 4, 1)
    await _seed(
        conn,
        user_id=uid,
        performed_at=_ts(today) + 10 * 3600,
        exercises=[
            _ex(
                "back_squat",
                "squat",
                [
                    (5, 60, True),  # warmup
                    (5, 80, True),  # warmup
                    (5, 100, False),  # working
                    (5, 100, False),  # working
                ],
            ),
        ],
    )
    data = await build_dashboard(
        conn,
        user_id=uid,
        since_ts=_ts(today),
        until_ts=_eod(today),
        filter_spec=FilterSpec(),
        catalog=catalog,
    )
    # Only working sets count: 5 + 5 = 10 reps at 100 kg
    assert data.kpsh_by_bucket["squat"][0] == 10
    assert data.intensity_kg[0] == 100.0
    assert data.kpsh_by_muscle["legs"] == 10


async def test_intensity_formula(conn) -> None:
    """5×100 + 3×110 → (5*100 + 3*110) / (5+3) = 830/8 = 103.75 kg."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    today = date(2026, 4, 1)
    await _seed(
        conn,
        user_id=uid,
        performed_at=_ts(today) + 10 * 3600,
        exercises=[
            _ex("bench_press", "push", [(5, 100, False), (3, 110, False)]),
        ],
    )
    data = await build_dashboard(
        conn,
        user_id=uid,
        since_ts=_ts(today),
        until_ts=_eod(today),
        filter_spec=FilterSpec(),
        catalog=catalog,
    )
    assert data.intensity_kg[0] == 103.75
    assert data.avg_intensity_kg == 103.75
    assert data.total_kpsh == 8
    assert data.kpsh_by_bucket["bench"][0] == 8


async def test_target_only_filter(conn) -> None:
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    today = date(2026, 4, 1)
    await _seed(
        conn,
        user_id=uid,
        performed_at=_ts(today) + 10 * 3600,
        exercises=[
            _ex("bench_press", "push", [(5, 100, False)]),
            _ex("dumbbell_fly", "push", [(12, 20, False)], position=1),
            _ex("bicep_curl", "accessory", [(10, 15, False)], position=2),
        ],
    )
    data = await build_dashboard(
        conn,
        user_id=uid,
        since_ts=_ts(today),
        until_ts=_eod(today),
        filter_spec=FilterSpec(target_only=True),
        catalog=catalog,
    )
    # Only bench_press has target_group=bench
    assert data.kpsh_by_bucket["bench"][0] == 5
    assert data.kpsh_by_bucket["other"][0] == 0
    assert data.total_kpsh == 5
    # Other muscle groups didn't pass the filter
    assert data.kpsh_by_muscle["chest"] == 5
    assert data.kpsh_by_muscle["arms"] == 0


async def test_muscle_group_filter(conn) -> None:
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    today = date(2026, 4, 1)
    await _seed(
        conn,
        user_id=uid,
        performed_at=_ts(today) + 10 * 3600,
        exercises=[
            _ex("bench_press", "push", [(5, 100, False)]),
            _ex("back_squat", "squat", [(5, 120, False)], position=1),
            _ex("dumbbell_fly", "push", [(12, 20, False)], position=2),
        ],
    )
    data = await build_dashboard(
        conn,
        user_id=uid,
        since_ts=_ts(today),
        until_ts=_eod(today),
        filter_spec=FilterSpec(muscle_groups=["chest"]),
        catalog=catalog,
    )
    # Only chest exercises remain: bench_press + dumbbell_fly
    assert data.kpsh_by_bucket["bench"][0] == 5
    assert data.kpsh_by_bucket["other"][0] == 12
    assert data.kpsh_by_bucket["squat"][0] == 0
    assert data.total_kpsh == 17
    assert data.kpsh_by_muscle["chest"] == 17
    assert data.kpsh_by_muscle["legs"] == 0


async def test_movement_pattern_filter_pull(conn) -> None:
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    today = date(2026, 4, 1)
    await _seed(
        conn,
        user_id=uid,
        performed_at=_ts(today) + 10 * 3600,
        exercises=[
            _ex("barbell_row", "pull", [(8, 80, False)]),
            _ex("bench_press", "push", [(5, 100, False)], position=1),
            _ex("lat_pulldown", "pull", [(10, 60, False)], position=2),
        ],
    )
    data = await build_dashboard(
        conn,
        user_id=uid,
        since_ts=_ts(today),
        until_ts=_eod(today),
        filter_spec=FilterSpec(movement_patterns=["pull"]),
        catalog=catalog,
    )
    assert data.kpsh_by_pattern == {"pull": 18}
    assert data.kpsh_by_bucket["other"][0] == 18
    assert data.kpsh_by_bucket["bench"][0] == 0


async def test_two_days_intensity_per_day(conn) -> None:
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    d1 = date(2026, 4, 1)
    d2 = date(2026, 4, 2)
    await _seed(
        conn,
        user_id=uid,
        performed_at=_ts(d1) + 10 * 3600,
        exercises=[_ex("bench_press", "push", [(5, 100, False)])],
    )
    await _seed(
        conn,
        user_id=uid,
        performed_at=_ts(d2) + 10 * 3600,
        exercises=[_ex("bench_press", "push", [(3, 120, False)])],
    )
    data = await build_dashboard(
        conn,
        user_id=uid,
        since_ts=_ts(d1),
        until_ts=_eod(d2),
        filter_spec=FilterSpec(),
        catalog=catalog,
    )
    assert data.days == [d1, d2]
    assert data.intensity_kg == [100.0, 120.0]
    assert data.total_kpsh == 8
    assert data.total_workouts == 2
    # avg = (5*100 + 3*120) / 8 = (500 + 360) / 8 = 107.5
    assert data.avg_intensity_kg == 107.5


async def test_unresolved_canonical_falls_into_other(conn) -> None:
    """An exercise without a catalog match should still be counted in 'other'."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    today = date(2026, 4, 1)
    await _seed(
        conn,
        user_id=uid,
        performed_at=_ts(today) + 10 * 3600,
        exercises=[
            _ex("nonexistent_exercise", "accessory", [(10, 20, False)]),
        ],
    )
    data = await build_dashboard(
        conn,
        user_id=uid,
        since_ts=_ts(today),
        until_ts=_eod(today),
        filter_spec=FilterSpec(),
        catalog=catalog,
    )
    assert data.kpsh_by_bucket["other"][0] == 10
    # No muscle_group attribution because catalog miss
    assert sum(data.kpsh_by_muscle.values()) == 0
    # Pattern attribution falls back to ExerciseRow.movement_pattern
    assert data.kpsh_by_pattern.get("accessory") == 10
