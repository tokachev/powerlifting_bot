from __future__ import annotations

import aiosqlite
import pytest

from pwrbot.db.connection import bootstrap
from pwrbot.db.repo import (
    ExerciseRow,
    SetRow,
    append_to_workout,
    delete_last_workout,
    get_last_workout,
    get_or_create_user,
    get_workouts_in_window,
    insert_workout,
    save_snapshot,
    workout_exists,
)


@pytest.fixture
async def conn():
    c = await aiosqlite.connect(":memory:")
    c.row_factory = aiosqlite.Row
    await c.execute("PRAGMA foreign_keys = ON")
    await bootstrap(c)
    try:
        yield c
    finally:
        await c.close()


def _sample_exercise(pos: int = 1) -> ExerciseRow:
    return ExerciseRow(
        position=pos,
        raw_name="присед",
        canonical_name="back_squat",
        movement_pattern="squat",
        sets=[
            SetRow(reps=5, weight_g=100_000, rpe=8.0, is_warmup=False, set_index=1),
            SetRow(reps=5, weight_g=100_000, rpe=8.5, is_warmup=False, set_index=2),
        ],
    )


async def test_get_or_create_user_idempotent(conn: aiosqlite.Connection) -> None:
    uid1 = await get_or_create_user(conn, telegram_id=42, display_name="tester")
    uid2 = await get_or_create_user(conn, telegram_id=42)
    assert uid1 == uid2


async def test_insert_and_fetch_workout(conn: aiosqlite.Connection, now_ts: int) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    wid = await insert_workout(
        conn,
        user_id=uid,
        performed_at=now_ts,
        source_text="присед 2x5x100",
        exercises=[_sample_exercise()],
    )
    assert wid > 0

    results = await get_workouts_in_window(
        conn, user_id=uid, since_ts=now_ts - 10, until_ts=now_ts + 10
    )
    assert len(results) == 1
    w = results[0]
    assert w.source_text == "присед 2x5x100"
    assert len(w.exercises) == 1
    assert w.exercises[0].canonical_name == "back_squat"
    assert len(w.exercises[0].sets) == 2
    assert w.exercises[0].sets[0].weight_g == 100_000


async def test_get_last_workout(conn: aiosqlite.Connection, now_ts: int) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    await insert_workout(
        conn,
        user_id=uid,
        performed_at=now_ts - 3600,
        source_text="old",
        exercises=[_sample_exercise()],
    )
    await insert_workout(
        conn,
        user_id=uid,
        performed_at=now_ts,
        source_text="new",
        exercises=[_sample_exercise()],
    )
    last = await get_last_workout(conn, user_id=uid)
    assert last is not None
    assert last.source_text == "new"


async def test_delete_last_workout_cascade(conn: aiosqlite.Connection, now_ts: int) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    await insert_workout(
        conn,
        user_id=uid,
        performed_at=now_ts,
        source_text="тест",
        exercises=[_sample_exercise()],
    )
    deleted_id = await delete_last_workout(conn, user_id=uid)
    assert deleted_id is not None

    # exercises and sets must be gone (CASCADE)
    row = await (await conn.execute("SELECT COUNT(*) AS c FROM exercise_entries")).fetchone()
    assert row["c"] == 0
    row = await (await conn.execute("SELECT COUNT(*) AS c FROM set_entries")).fetchone()
    assert row["c"] == 0


async def test_append_to_workout(conn: aiosqlite.Connection, now_ts: int) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    wid = await insert_workout(
        conn,
        user_id=uid,
        performed_at=now_ts,
        source_text="присед 2x5x100",
        exercises=[_sample_exercise(pos=1)],
    )

    extra = ExerciseRow(
        position=1,  # ignored — append_to_workout auto-offsets
        raw_name="подтягивания",
        canonical_name="pullup",
        movement_pattern="pull",
        sets=[
            SetRow(reps=8, weight_g=0, rpe=None, is_warmup=False, set_index=1),
            SetRow(reps=8, weight_g=0, rpe=None, is_warmup=False, set_index=2),
        ],
    )
    new_ids = await append_to_workout(
        conn,
        workout_id=wid,
        exercises=[extra],
        addition_text="подтягивания 2x8",
    )
    assert len(new_ids) == 1

    results = await get_workouts_in_window(
        conn, user_id=uid, since_ts=now_ts - 10, until_ts=now_ts + 10
    )
    assert len(results) == 1
    w = results[0]
    assert w.source_text == "присед 2x5x100\nподтягивания 2x8"
    assert [ex.position for ex in w.exercises] == [1, 2]
    assert w.exercises[1].canonical_name == "pullup"
    assert len(w.exercises[1].sets) == 2

    # Re-append: positions keep advancing
    await append_to_workout(
        conn,
        workout_id=wid,
        exercises=[
            ExerciseRow(
                position=99, raw_name="планка", canonical_name=None,
                movement_pattern=None,
                sets=[SetRow(reps=60, weight_g=0, rpe=None, is_warmup=False, set_index=1)],
            )
        ],
    )
    w = (await get_workouts_in_window(
        conn, user_id=uid, since_ts=now_ts - 10, until_ts=now_ts + 10
    ))[0]
    assert [ex.position for ex in w.exercises] == [1, 2, 3]


async def test_workout_exists(conn: aiosqlite.Connection, now_ts: int) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    other_uid = await get_or_create_user(conn, telegram_id=43)
    wid = await insert_workout(
        conn, user_id=uid, performed_at=now_ts,
        source_text="x", exercises=[_sample_exercise()],
    )
    assert await workout_exists(conn, workout_id=wid, user_id=uid) is True
    # Same workout id but different user must NOT match (owner check matters
    # for the clarify-FSM "did this workout get deleted while I was clicking" guard).
    assert await workout_exists(conn, workout_id=wid, user_id=other_uid) is False
    assert await workout_exists(conn, workout_id=99999, user_id=uid) is False


async def test_save_snapshot_roundtrip(conn: aiosqlite.Connection) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    sid = await save_snapshot(
        conn,
        user_id=uid,
        window_days=7,
        metrics={"tonnage_kg": 1234.5, "hard_sets": {"squat": 5}},
        flags=[{"kind": "recovery_risk", "pattern": "squat"}],
        explanation="всё норм",
    )
    assert sid > 0
    row = await (
        await conn.execute("SELECT metrics_json, flags_json, explanation FROM analysis_snapshots")
    ).fetchone()
    assert "tonnage_kg" in row["metrics_json"]
    assert "recovery_risk" in row["flags_json"]
    assert row["explanation"] == "всё норм"
