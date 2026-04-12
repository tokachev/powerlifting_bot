"""Integration tests for personal records repo functions."""

import pytest

from pwrbot.db import repo


@pytest.fixture()
async def user_id(conn):
    return await repo.get_or_create_user(conn, telegram_id=111)


@pytest.fixture()
async def workout_id(conn, user_id):
    return await repo.insert_workout(
        conn,
        user_id=user_id,
        performed_at=1_700_000_000,
        source_text="присед 3x5x100",
        exercises=[
            repo.ExerciseRow(
                position=0,
                raw_name="присед",
                canonical_name="back_squat",
                movement_pattern="squat",
                sets=[repo.SetRow(reps=5, weight_g=100_000, rpe=None, is_warmup=False, set_index=0)],
            )
        ],
    )


async def test_insert_and_get(conn, user_id, workout_id):
    pr_id = await repo.insert_personal_record(
        conn,
        user_id=user_id,
        canonical_name="back_squat",
        pr_type="e1rm",
        weight_g=100_000,
        reps=5,
        estimated_1rm_g=116_700,
        previous_value_g=None,
        workout_id=workout_id,
        achieved_at=1_700_000_000,
    )
    assert pr_id > 0

    records = await repo.get_personal_records(conn, user_id=user_id)
    assert len(records) == 1
    r = records[0]
    assert r.canonical_name == "back_squat"
    assert r.pr_type == "e1rm"
    assert r.weight_g == 100_000
    assert r.reps == 5
    assert r.estimated_1rm_g == 116_700
    assert r.previous_value_g is None
    assert r.workout_id == workout_id


async def test_get_best_e1rm(conn, user_id, workout_id):
    await repo.insert_personal_record(
        conn, user_id=user_id, canonical_name="back_squat",
        pr_type="e1rm", weight_g=100_000, reps=5,
        estimated_1rm_g=116_700, previous_value_g=None,
        workout_id=workout_id, achieved_at=1_700_000_000,
    )
    await repo.insert_personal_record(
        conn, user_id=user_id, canonical_name="back_squat",
        pr_type="e1rm", weight_g=110_000, reps=3,
        estimated_1rm_g=120_000, previous_value_g=116_700,
        workout_id=workout_id, achieved_at=1_700_001_000,
    )

    best = await repo.get_best_e1rm_for_exercise(
        conn, user_id=user_id, canonical_name="back_squat",
    )
    assert best == 120_000


async def test_get_best_e1rm_no_records(conn, user_id):
    best = await repo.get_best_e1rm_for_exercise(
        conn, user_id=user_id, canonical_name="deadlift",
    )
    assert best is None


async def test_filter_by_since(conn, user_id, workout_id):
    await repo.insert_personal_record(
        conn, user_id=user_id, canonical_name="back_squat",
        pr_type="e1rm", weight_g=100_000, reps=5,
        estimated_1rm_g=116_700, previous_value_g=None,
        workout_id=workout_id, achieved_at=1_700_000_000,
    )
    # Should NOT be returned if since_ts is later
    records = await repo.get_personal_records(
        conn, user_id=user_id, since_ts=1_700_001_000,
    )
    assert len(records) == 0

    # Should be returned if since_ts is earlier
    records = await repo.get_personal_records(
        conn, user_id=user_id, since_ts=1_699_999_000,
    )
    assert len(records) == 1


async def test_filter_by_canonical_name(conn, user_id, workout_id):
    await repo.insert_personal_record(
        conn, user_id=user_id, canonical_name="back_squat",
        pr_type="e1rm", weight_g=100_000, reps=5,
        estimated_1rm_g=116_700, previous_value_g=None,
        workout_id=workout_id, achieved_at=1_700_000_000,
    )
    records = await repo.get_personal_records(
        conn, user_id=user_id, canonical_name="deadlift",
    )
    assert len(records) == 0

    records = await repo.get_personal_records(
        conn, user_id=user_id, canonical_name="back_squat",
    )
    assert len(records) == 1
