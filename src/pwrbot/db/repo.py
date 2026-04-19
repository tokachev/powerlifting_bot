"""CRUD + window queries for workouts, exercises, sets and analysis snapshots.

All weight values at the repo boundary are integers in grams.
All timestamps are integer unix seconds.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import aiosqlite

# ------------------------------------------------------------------ DTOs


@dataclass(slots=True)
class SetRow:
    reps: int
    weight_g: int
    rpe: float | None
    is_warmup: bool
    set_index: int
    bar_velocity_ms: float | None = None


@dataclass(slots=True)
class ExerciseRow:
    position: int
    raw_name: str
    canonical_name: str | None
    movement_pattern: str | None
    sets: list[SetRow]


@dataclass(slots=True)
class WorkoutRow:
    id: int
    user_id: int
    performed_at: int
    logged_at: int
    source_text: str
    notes: str | None
    exercises: list[ExerciseRow]


# ------------------------------------------------------------------ users


async def get_or_create_user(
    conn: aiosqlite.Connection, telegram_id: int, display_name: str | None = None
) -> int:
    row = await (
        await conn.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    ).fetchone()
    if row is not None:
        return int(row["id"])
    cursor = await conn.execute(
        "INSERT INTO users (telegram_id, display_name, created_at) VALUES (?, ?, ?)",
        (telegram_id, display_name, int(time.time())),
    )
    await conn.commit()
    return int(cursor.lastrowid)


# ------------------------------------------------------------------ workouts


async def insert_workout(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    performed_at: int,
    source_text: str,
    exercises: list[ExerciseRow],
    notes: str | None = None,
) -> int:
    """Insert a workout with all its exercises and sets in one transaction."""
    now = int(time.time())
    async with conn.execute(
        "INSERT INTO workouts (user_id, performed_at, logged_at, source_text, notes) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, performed_at, now, source_text, notes),
    ) as cur:
        workout_id = int(cur.lastrowid)

    for ex in exercises:
        async with conn.execute(
            "INSERT INTO exercise_entries "
            "(workout_id, position, raw_name, canonical_name, movement_pattern) "
            "VALUES (?, ?, ?, ?, ?)",
            (workout_id, ex.position, ex.raw_name, ex.canonical_name, ex.movement_pattern),
        ) as cur:
            exercise_entry_id = int(cur.lastrowid)
        for s in ex.sets:
            await conn.execute(
                "INSERT INTO set_entries "
                "(exercise_entry_id, set_index, reps, weight_g, rpe, is_warmup, "
                "bar_velocity_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    exercise_entry_id,
                    s.set_index,
                    s.reps,
                    s.weight_g,
                    s.rpe,
                    1 if s.is_warmup else 0,
                    s.bar_velocity_ms,
                ),
            )
    await conn.commit()
    return workout_id


async def get_workouts_in_window(
    conn: aiosqlite.Connection, *, user_id: int, since_ts: int, until_ts: int
) -> list[WorkoutRow]:
    """Return workouts in [since_ts, until_ts] hydrated with exercises and sets."""
    workouts: dict[int, WorkoutRow] = {}
    async with conn.execute(
        "SELECT id, user_id, performed_at, logged_at, source_text, notes "
        "FROM workouts WHERE user_id = ? AND performed_at >= ? AND performed_at <= ? "
        "ORDER BY performed_at ASC, id ASC",
        (user_id, since_ts, until_ts),
    ) as cur:
        async for row in cur:
            workouts[int(row["id"])] = WorkoutRow(
                id=int(row["id"]),
                user_id=int(row["user_id"]),
                performed_at=int(row["performed_at"]),
                logged_at=int(row["logged_at"]),
                source_text=row["source_text"],
                notes=row["notes"],
                exercises=[],
            )
    if not workouts:
        return []

    placeholders = ",".join("?" * len(workouts))
    ex_by_id: dict[int, tuple[int, ExerciseRow]] = {}
    async with conn.execute(
        f"SELECT id, workout_id, position, raw_name, canonical_name, movement_pattern "
        f"FROM exercise_entries WHERE workout_id IN ({placeholders}) "
        f"ORDER BY workout_id ASC, position ASC",
        tuple(workouts.keys()),
    ) as cur:
        async for row in cur:
            ex = ExerciseRow(
                position=int(row["position"]),
                raw_name=row["raw_name"],
                canonical_name=row["canonical_name"],
                movement_pattern=row["movement_pattern"],
                sets=[],
            )
            ex_by_id[int(row["id"])] = (int(row["workout_id"]), ex)
            workouts[int(row["workout_id"])].exercises.append(ex)

    if not ex_by_id:
        return list(workouts.values())

    placeholders = ",".join("?" * len(ex_by_id))
    async with conn.execute(
        f"SELECT exercise_entry_id, set_index, reps, weight_g, rpe, is_warmup, "
        f"bar_velocity_ms "
        f"FROM set_entries WHERE exercise_entry_id IN ({placeholders}) "
        f"ORDER BY exercise_entry_id ASC, set_index ASC",
        tuple(ex_by_id.keys()),
    ) as cur:
        async for row in cur:
            _, ex = ex_by_id[int(row["exercise_entry_id"])]
            ex.sets.append(
                SetRow(
                    reps=int(row["reps"]),
                    weight_g=int(row["weight_g"]),
                    rpe=row["rpe"],
                    is_warmup=bool(row["is_warmup"]),
                    set_index=int(row["set_index"]),
                    bar_velocity_ms=(
                        float(row["bar_velocity_ms"])
                        if row["bar_velocity_ms"] is not None
                        else None
                    ),
                )
            )

    return list(workouts.values())


async def append_to_workout(
    conn: aiosqlite.Connection,
    *,
    workout_id: int,
    exercises: list[ExerciseRow],
    addition_text: str | None = None,
) -> list[int]:
    """Append exercises to an existing workout.

    Position numbers in the input ``exercises`` are ignored — the function
    auto-offsets new entries to start right after the current MAX(position),
    so concurrent inserts can't violate the UNIQUE(workout_id, position) index.

    If ``addition_text`` is given, it is appended to the workout's source_text
    on a new line so the audit trail keeps the user's exact wording.

    Returns the new exercise_entry ids in insertion order.
    """
    row = await (
        await conn.execute(
            "SELECT COALESCE(MAX(position), 0) AS m "
            "FROM exercise_entries WHERE workout_id = ?",
            (workout_id,),
        )
    ).fetchone()
    offset = int(row["m"]) if row is not None else 0

    new_ids: list[int] = []
    for i, ex in enumerate(exercises, start=1):
        async with conn.execute(
            "INSERT INTO exercise_entries "
            "(workout_id, position, raw_name, canonical_name, movement_pattern) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                workout_id,
                offset + i,
                ex.raw_name,
                ex.canonical_name,
                ex.movement_pattern,
            ),
        ) as cur:
            entry_id = int(cur.lastrowid)
        new_ids.append(entry_id)
        for s in ex.sets:
            await conn.execute(
                "INSERT INTO set_entries "
                "(exercise_entry_id, set_index, reps, weight_g, rpe, is_warmup, "
                "bar_velocity_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entry_id,
                    s.set_index,
                    s.reps,
                    s.weight_g,
                    s.rpe,
                    1 if s.is_warmup else 0,
                    s.bar_velocity_ms,
                ),
            )

    if addition_text:
        await conn.execute(
            "UPDATE workouts SET source_text = source_text || ? WHERE id = ?",
            ("\n" + addition_text, workout_id),
        )

    await conn.commit()
    return new_ids


async def workout_exists(
    conn: aiosqlite.Connection, *, workout_id: int, user_id: int
) -> bool:
    row = await (
        await conn.execute(
            "SELECT 1 FROM workouts WHERE id = ? AND user_id = ?",
            (workout_id, user_id),
        )
    ).fetchone()
    return row is not None


async def get_last_workout(
    conn: aiosqlite.Connection, user_id: int
) -> WorkoutRow | None:
    row = await (
        await conn.execute(
            "SELECT id, performed_at FROM workouts WHERE user_id = ? "
            "ORDER BY performed_at DESC, id DESC LIMIT 1",
            (user_id,),
        )
    ).fetchone()
    if row is None:
        return None
    performed_at = int(row["performed_at"])
    results = await get_workouts_in_window(
        conn, user_id=user_id, since_ts=performed_at, until_ts=performed_at
    )
    # Same-second collisions are possible, filter by id.
    wanted_id = int(row["id"])
    for w in results:
        if w.id == wanted_id:
            return w
    return None


async def delete_last_workout(conn: aiosqlite.Connection, user_id: int) -> int | None:
    row = await (
        await conn.execute(
            "SELECT id FROM workouts WHERE user_id = ? "
            "ORDER BY performed_at DESC, id DESC LIMIT 1",
            (user_id,),
        )
    ).fetchone()
    if row is None:
        return None
    workout_id = int(row["id"])
    await conn.execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
    await conn.commit()
    return workout_id


# ------------------------------------------------------------------ analysis snapshots


async def save_snapshot(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    window_days: int,
    metrics: dict[str, Any],
    flags: list[dict[str, Any]],
    explanation: str | None = None,
) -> int:
    cursor = await conn.execute(
        "INSERT INTO analysis_snapshots "
        "(user_id, window_days, computed_at, metrics_json, flags_json, explanation) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            user_id,
            window_days,
            int(time.time()),
            json.dumps(metrics, ensure_ascii=False),
            json.dumps(flags, ensure_ascii=False),
            explanation,
        ),
    )
    await conn.commit()
    return int(cursor.lastrowid)


# ------------------------------------------------------------------ body weight


async def upsert_body_weight(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    recorded_at: int,
    weight_g: int,
) -> int:
    """Insert or update body weight for a given date (one per user per day)."""
    cursor = await conn.execute(
        "INSERT INTO body_weight (user_id, recorded_at, weight_g, logged_at) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, recorded_at) DO UPDATE SET weight_g = excluded.weight_g, "
        "logged_at = excluded.logged_at",
        (user_id, recorded_at, weight_g, int(time.time())),
    )
    await conn.commit()
    return int(cursor.lastrowid)


async def get_latest_body_weight(
    conn: aiosqlite.Connection, user_id: int
) -> tuple[int, int] | None:
    """Return (weight_g, recorded_at) of the most recent entry, or None."""
    row = await (
        await conn.execute(
            "SELECT weight_g, recorded_at FROM body_weight "
            "WHERE user_id = ? ORDER BY recorded_at DESC LIMIT 1",
            (user_id,),
        )
    ).fetchone()
    if row is None:
        return None
    return int(row["weight_g"]), int(row["recorded_at"])


async def get_body_weight_at(
    conn: aiosqlite.Connection, user_id: int, at_ts: int
) -> int | None:
    """Return weight_g of the entry closest to (but not after) at_ts, or None."""
    row = await (
        await conn.execute(
            "SELECT weight_g FROM body_weight "
            "WHERE user_id = ? AND recorded_at <= ? "
            "ORDER BY recorded_at DESC LIMIT 1",
            (user_id, at_ts),
        )
    ).fetchone()
    if row is None:
        return None
    return int(row["weight_g"])


async def get_body_weight_history(
    conn: aiosqlite.Connection, *, user_id: int, since_ts: int, until_ts: int
) -> list[tuple[int, int]]:
    """Return list of (recorded_at, weight_g) in ascending date order."""
    rows = await (
        await conn.execute(
            "SELECT recorded_at, weight_g FROM body_weight "
            "WHERE user_id = ? AND recorded_at >= ? AND recorded_at <= ? "
            "ORDER BY recorded_at ASC",
            (user_id, since_ts, until_ts),
        )
    ).fetchall()
    return [(int(r["recorded_at"]), int(r["weight_g"])) for r in rows]


# ------------------------------------------------------------------ personal records


@dataclass(slots=True)
class PersonalRecordRow:
    id: int
    user_id: int
    canonical_name: str
    pr_type: str
    weight_g: int
    reps: int
    estimated_1rm_g: int
    previous_value_g: int | None
    workout_id: int
    achieved_at: int


async def insert_personal_record(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    canonical_name: str,
    pr_type: str,
    weight_g: int,
    reps: int,
    estimated_1rm_g: int,
    previous_value_g: int | None,
    workout_id: int,
    achieved_at: int,
) -> int:
    """Insert a new personal record. Returns the row id."""
    cursor = await conn.execute(
        "INSERT INTO personal_records "
        "(user_id, canonical_name, pr_type, weight_g, reps, "
        "estimated_1rm_g, previous_value_g, workout_id, achieved_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            canonical_name,
            pr_type,
            weight_g,
            reps,
            estimated_1rm_g,
            previous_value_g,
            workout_id,
            achieved_at,
        ),
    )
    await conn.commit()
    return int(cursor.lastrowid)


async def get_personal_records(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    since_ts: int | None = None,
    canonical_name: str | None = None,
    limit: int = 50,
) -> list[PersonalRecordRow]:
    """Return PRs for a user, optionally filtered by time and exercise."""
    clauses = ["user_id = ?"]
    params: list[int | str] = [user_id]
    if since_ts is not None:
        clauses.append("achieved_at >= ?")
        params.append(since_ts)
    if canonical_name is not None:
        clauses.append("canonical_name = ?")
        params.append(canonical_name)
    where = " AND ".join(clauses)
    rows = await (
        await conn.execute(
            f"SELECT id, user_id, canonical_name, pr_type, weight_g, reps, "
            f"estimated_1rm_g, previous_value_g, workout_id, achieved_at "
            f"FROM personal_records WHERE {where} "
            f"ORDER BY achieved_at DESC LIMIT ?",
            (*params, limit),
        )
    ).fetchall()
    return [
        PersonalRecordRow(
            id=int(r["id"]),
            user_id=int(r["user_id"]),
            canonical_name=r["canonical_name"],
            pr_type=r["pr_type"],
            weight_g=int(r["weight_g"]),
            reps=int(r["reps"]),
            estimated_1rm_g=int(r["estimated_1rm_g"]),
            previous_value_g=int(r["previous_value_g"]) if r["previous_value_g"] is not None else None,
            workout_id=int(r["workout_id"]),
            achieved_at=int(r["achieved_at"]),
        )
        for r in rows
    ]


async def get_best_e1rm_for_exercise(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    canonical_name: str,
) -> int | None:
    """Return the highest estimated_1rm_g ever recorded for this user+exercise, or None."""
    row = await (
        await conn.execute(
            "SELECT MAX(estimated_1rm_g) AS best "
            "FROM personal_records "
            "WHERE user_id = ? AND canonical_name = ? AND pr_type = 'e1rm'",
            (user_id, canonical_name),
        )
    ).fetchone()
    if row is None or row["best"] is None:
        return None
    return int(row["best"])


# -------------------------------------------------- video analyses


@dataclass(slots=True)
class VideoAnalysisRow:
    id: int
    user_id: int
    exercise_hint: str | None
    frame_count: int
    duration_s: float
    analysis_text: str
    model_used: str
    analyzed_at: int
    telegram_file_id: str | None


async def insert_video_analysis(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    exercise_hint: str | None,
    frame_count: int,
    duration_s: float,
    analysis_text: str,
    model_used: str,
    telegram_file_id: str | None = None,
) -> int:
    cur = await conn.execute(
        "INSERT INTO video_analyses "
        "(user_id, exercise_hint, frame_count, duration_s, analysis_text, "
        " model_used, analyzed_at, telegram_file_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            exercise_hint,
            frame_count,
            duration_s,
            analysis_text,
            model_used,
            int(time.time()),
            telegram_file_id,
        ),
    )
    await conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


async def get_video_analyses(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    limit: int = 10,
) -> list[VideoAnalysisRow]:
    rows = await (
        await conn.execute(
            "SELECT * FROM video_analyses "
            "WHERE user_id = ? ORDER BY analyzed_at DESC LIMIT ?",
            (user_id, limit),
        )
    ).fetchall()
    return [
        VideoAnalysisRow(
            id=int(r["id"]),
            user_id=int(r["user_id"]),
            exercise_hint=r["exercise_hint"],
            frame_count=int(r["frame_count"]),
            duration_s=float(r["duration_s"]),
            analysis_text=r["analysis_text"],
            model_used=r["model_used"],
            analyzed_at=int(r["analyzed_at"]),
            telegram_file_id=r["telegram_file_id"],
        )
        for r in rows
    ]
