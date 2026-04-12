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
                "(exercise_entry_id, set_index, reps, weight_g, rpe, is_warmup) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    exercise_entry_id,
                    s.set_index,
                    s.reps,
                    s.weight_g,
                    s.rpe,
                    1 if s.is_warmup else 0,
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
        f"SELECT exercise_entry_id, set_index, reps, weight_g, rpe, is_warmup "
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
                )
            )

    return list(workouts.values())


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
