"""CRUD for powerlifting-specific tables: meets, recovery, niggles, technique, phases.

Weights at the repo boundary are grams (int). Timestamps are unix seconds (int).
Dates are stored as midnight UTC unix seconds.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime

import aiosqlite


def date_to_unix(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


def unix_to_date(ts: int) -> date:
    return datetime.fromtimestamp(ts, tz=UTC).date()


# ------------------------------------------------------------------ meets


@dataclass(slots=True)
class MeetAttemptRow:
    id: int
    meet_id: int
    lift: str
    attempt_no: int
    weight_g: int
    status: str


@dataclass(slots=True)
class MeetRow:
    id: int
    user_id: int
    meet_date: int
    name: str
    category: str | None
    federation: str | None
    bodyweight_g: int | None
    squat_g: int
    bench_g: int
    deadlift_g: int
    total_g: int
    wilks: float | None
    dots: float | None
    ipf_gl: float | None
    place: int | None
    is_gym_meet: bool
    notes: str | None
    attempts: list[MeetAttemptRow]


async def list_meets(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    since_ts: int | None = None,
    until_ts: int | None = None,
) -> list[MeetRow]:
    clauses = ["user_id = ?"]
    params: list[int] = [user_id]
    if since_ts is not None:
        clauses.append("meet_date >= ?")
        params.append(since_ts)
    if until_ts is not None:
        clauses.append("meet_date <= ?")
        params.append(until_ts)
    where = " AND ".join(clauses)
    meets: dict[int, MeetRow] = {}
    async with conn.execute(
        f"SELECT id, user_id, meet_date, name, category, federation, bodyweight_g, "
        f"squat_g, bench_g, deadlift_g, total_g, wilks, dots, ipf_gl, place, "
        f"is_gym_meet, notes FROM meets WHERE {where} ORDER BY meet_date ASC, id ASC",
        tuple(params),
    ) as cur:
        async for r in cur:
            meets[int(r["id"])] = MeetRow(
                id=int(r["id"]),
                user_id=int(r["user_id"]),
                meet_date=int(r["meet_date"]),
                name=r["name"],
                category=r["category"],
                federation=r["federation"],
                bodyweight_g=int(r["bodyweight_g"]) if r["bodyweight_g"] is not None else None,
                squat_g=int(r["squat_g"]),
                bench_g=int(r["bench_g"]),
                deadlift_g=int(r["deadlift_g"]),
                total_g=int(r["total_g"]),
                wilks=float(r["wilks"]) if r["wilks"] is not None else None,
                dots=float(r["dots"]) if r["dots"] is not None else None,
                ipf_gl=float(r["ipf_gl"]) if r["ipf_gl"] is not None else None,
                place=int(r["place"]) if r["place"] is not None else None,
                is_gym_meet=bool(r["is_gym_meet"]),
                notes=r["notes"],
                attempts=[],
            )
    if not meets:
        return []

    placeholders = ",".join("?" * len(meets))
    async with conn.execute(
        f"SELECT id, meet_id, lift, attempt_no, weight_g, status "
        f"FROM meet_attempts WHERE meet_id IN ({placeholders}) "
        f"ORDER BY meet_id ASC, lift ASC, attempt_no ASC",
        tuple(meets.keys()),
    ) as cur:
        async for r in cur:
            meet_id = int(r["meet_id"])
            if meet_id in meets:
                meets[meet_id].attempts.append(
                    MeetAttemptRow(
                        id=int(r["id"]),
                        meet_id=meet_id,
                        lift=r["lift"],
                        attempt_no=int(r["attempt_no"]),
                        weight_g=int(r["weight_g"]),
                        status=r["status"],
                    )
                )
    return list(meets.values())


async def insert_meet(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    meet_date: int,
    name: str,
    category: str | None,
    federation: str | None,
    bodyweight_g: int | None,
    squat_g: int,
    bench_g: int,
    deadlift_g: int,
    wilks: float | None,
    dots: float | None,
    ipf_gl: float | None,
    place: int | None,
    is_gym_meet: bool,
    notes: str | None,
    attempts: list[MeetAttemptRow] | None = None,
) -> int:
    total_g = squat_g + bench_g + deadlift_g
    cur = await conn.execute(
        "INSERT INTO meets (user_id, meet_date, name, category, federation, bodyweight_g, "
        "squat_g, bench_g, deadlift_g, total_g, wilks, dots, ipf_gl, place, is_gym_meet, "
        "notes, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id, meet_date, name, category, federation, bodyweight_g,
            squat_g, bench_g, deadlift_g, total_g, wilks, dots, ipf_gl, place,
            1 if is_gym_meet else 0, notes, int(time.time()),
        ),
    )
    meet_id = int(cur.lastrowid)  # type: ignore[arg-type]
    if attempts:
        for a in attempts:
            await conn.execute(
                "INSERT INTO meet_attempts (meet_id, lift, attempt_no, weight_g, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (meet_id, a.lift, a.attempt_no, a.weight_g, a.status),
            )
    await conn.commit()
    return meet_id


# ------------------------------------------------------------------ next meet


@dataclass(slots=True)
class NextMeetRow:
    user_id: int
    meet_date: int
    name: str
    category: str | None
    federation: str | None
    target_squat_g: int
    target_bench_g: int
    target_deadlift_g: int
    attempts: dict[str, list[int]]  # {squat: [g, g, g], bench: [...], deadlift: [...]}
    updated_at: int


async def get_next_meet(
    conn: aiosqlite.Connection, user_id: int
) -> NextMeetRow | None:
    row = await (
        await conn.execute(
            "SELECT user_id, meet_date, name, category, federation, target_squat_g, "
            "target_bench_g, target_deadlift_g, attempts_json, updated_at "
            "FROM next_meet_config WHERE user_id = ?",
            (user_id,),
        )
    ).fetchone()
    if row is None:
        return None
    attempts_raw = row["attempts_json"]
    attempts: dict[str, list[int]] = {"squat": [], "bench": [], "deadlift": []}
    if attempts_raw:
        try:
            loaded = json.loads(attempts_raw)
            if isinstance(loaded, dict):
                for lift in ("squat", "bench", "deadlift"):
                    vals = loaded.get(lift, [])
                    if isinstance(vals, list):
                        attempts[lift] = [int(v) for v in vals[:3]]
        except (ValueError, TypeError):
            pass
    return NextMeetRow(
        user_id=int(row["user_id"]),
        meet_date=int(row["meet_date"]),
        name=row["name"],
        category=row["category"],
        federation=row["federation"],
        target_squat_g=int(row["target_squat_g"]),
        target_bench_g=int(row["target_bench_g"]),
        target_deadlift_g=int(row["target_deadlift_g"]),
        attempts=attempts,
        updated_at=int(row["updated_at"]),
    )


async def upsert_next_meet(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    meet_date: int,
    name: str,
    category: str | None,
    federation: str | None,
    target_squat_g: int,
    target_bench_g: int,
    target_deadlift_g: int,
    attempts: dict[str, list[int]],
) -> None:
    await conn.execute(
        "INSERT INTO next_meet_config (user_id, meet_date, name, category, federation, "
        "target_squat_g, target_bench_g, target_deadlift_g, attempts_json, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET meet_date=excluded.meet_date, "
        "name=excluded.name, category=excluded.category, federation=excluded.federation, "
        "target_squat_g=excluded.target_squat_g, target_bench_g=excluded.target_bench_g, "
        "target_deadlift_g=excluded.target_deadlift_g, attempts_json=excluded.attempts_json, "
        "updated_at=excluded.updated_at",
        (
            user_id, meet_date, name, category, federation,
            target_squat_g, target_bench_g, target_deadlift_g,
            json.dumps(attempts, ensure_ascii=False), int(time.time()),
        ),
    )
    await conn.commit()


# ------------------------------------------------------------------ recovery


@dataclass(slots=True)
class RecoveryRow:
    id: int
    user_id: int
    recorded_date: int
    sleep_hours: float | None
    hrv_ms: float | None
    rhr_bpm: int | None
    recovery_pct: int | None
    notes: str | None


async def list_recovery(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    since_ts: int | None = None,
    until_ts: int | None = None,
) -> list[RecoveryRow]:
    clauses = ["user_id = ?"]
    params: list[int] = [user_id]
    if since_ts is not None:
        clauses.append("recorded_date >= ?")
        params.append(since_ts)
    if until_ts is not None:
        clauses.append("recorded_date <= ?")
        params.append(until_ts)
    where = " AND ".join(clauses)
    rows = await (
        await conn.execute(
            f"SELECT id, user_id, recorded_date, sleep_hours, hrv_ms, rhr_bpm, "
            f"recovery_pct, notes FROM recovery_logs WHERE {where} "
            f"ORDER BY recorded_date ASC",
            tuple(params),
        )
    ).fetchall()
    return [
        RecoveryRow(
            id=int(r["id"]),
            user_id=int(r["user_id"]),
            recorded_date=int(r["recorded_date"]),
            sleep_hours=float(r["sleep_hours"]) if r["sleep_hours"] is not None else None,
            hrv_ms=float(r["hrv_ms"]) if r["hrv_ms"] is not None else None,
            rhr_bpm=int(r["rhr_bpm"]) if r["rhr_bpm"] is not None else None,
            recovery_pct=int(r["recovery_pct"]) if r["recovery_pct"] is not None else None,
            notes=r["notes"],
        )
        for r in rows
    ]


async def insert_recovery(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    recorded_date: int,
    sleep_hours: float | None,
    hrv_ms: float | None,
    rhr_bpm: int | None,
    recovery_pct: int | None,
    notes: str | None,
) -> int:
    cur = await conn.execute(
        "INSERT INTO recovery_logs (user_id, recorded_date, sleep_hours, hrv_ms, "
        "rhr_bpm, recovery_pct, notes, logged_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, recorded_date) DO UPDATE SET "
        "sleep_hours=excluded.sleep_hours, hrv_ms=excluded.hrv_ms, "
        "rhr_bpm=excluded.rhr_bpm, recovery_pct=excluded.recovery_pct, "
        "notes=excluded.notes, logged_at=excluded.logged_at",
        (
            user_id, recorded_date, sleep_hours, hrv_ms, rhr_bpm,
            recovery_pct, notes, int(time.time()),
        ),
    )
    await conn.commit()
    return int(cur.lastrowid)  # type: ignore[return-value]


# ------------------------------------------------------------------ niggles


@dataclass(slots=True)
class NiggleRow:
    id: int
    user_id: int
    recorded_date: int
    body_area: str
    severity: str
    note: str | None
    resolved_at: int | None


async def list_niggles(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    active_only: bool = True,
    limit: int = 50,
) -> list[NiggleRow]:
    clauses = ["user_id = ?"]
    params: list[int] = [user_id]
    if active_only:
        clauses.append("resolved_at IS NULL")
    where = " AND ".join(clauses)
    rows = await (
        await conn.execute(
            f"SELECT id, user_id, recorded_date, body_area, severity, note, resolved_at "
            f"FROM niggles WHERE {where} ORDER BY recorded_date DESC LIMIT ?",
            (*params, limit),
        )
    ).fetchall()
    return [
        NiggleRow(
            id=int(r["id"]),
            user_id=int(r["user_id"]),
            recorded_date=int(r["recorded_date"]),
            body_area=r["body_area"],
            severity=r["severity"],
            note=r["note"],
            resolved_at=int(r["resolved_at"]) if r["resolved_at"] is not None else None,
        )
        for r in rows
    ]


async def insert_niggle(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    recorded_date: int,
    body_area: str,
    severity: str,
    note: str | None,
) -> int:
    cur = await conn.execute(
        "INSERT INTO niggles (user_id, recorded_date, body_area, severity, note, logged_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, recorded_date, body_area, severity, note, int(time.time())),
    )
    await conn.commit()
    return int(cur.lastrowid)  # type: ignore[return-value]


async def resolve_niggle(conn: aiosqlite.Connection, niggle_id: int) -> None:
    await conn.execute(
        "UPDATE niggles SET resolved_at = ? WHERE id = ?",
        (int(time.time()), niggle_id),
    )
    await conn.commit()


# ------------------------------------------------------------------ technique notes


@dataclass(slots=True)
class TechniqueNoteRow:
    id: int
    user_id: int
    canonical_name: str
    recorded_date: int
    note_text: str
    source: str


async def list_technique_notes(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    canonical_name: str | None = None,
    limit: int = 20,
) -> list[TechniqueNoteRow]:
    clauses = ["user_id = ?"]
    params: list[int | str] = [user_id]
    if canonical_name is not None:
        clauses.append("canonical_name = ?")
        params.append(canonical_name)
    where = " AND ".join(clauses)
    rows = await (
        await conn.execute(
            f"SELECT id, user_id, canonical_name, recorded_date, note_text, source "
            f"FROM technique_notes WHERE {where} ORDER BY recorded_date DESC LIMIT ?",
            (*params, limit),
        )
    ).fetchall()
    return [
        TechniqueNoteRow(
            id=int(r["id"]),
            user_id=int(r["user_id"]),
            canonical_name=r["canonical_name"],
            recorded_date=int(r["recorded_date"]),
            note_text=r["note_text"],
            source=r["source"],
        )
        for r in rows
    ]


async def insert_technique_note(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    canonical_name: str,
    recorded_date: int,
    note_text: str,
    source: str = "user",
) -> int:
    cur = await conn.execute(
        "INSERT INTO technique_notes (user_id, canonical_name, recorded_date, "
        "note_text, source, logged_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, canonical_name, recorded_date, note_text, source, int(time.time())),
    )
    await conn.commit()
    return int(cur.lastrowid)  # type: ignore[return-value]


# ------------------------------------------------------------------ training phases


@dataclass(slots=True)
class PhaseRow:
    id: int
    user_id: int
    phase_name: str
    start_date: int
    end_date: int
    color_hex: str | None
    notes: str | None


async def list_phases(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    since_ts: int | None = None,
    until_ts: int | None = None,
) -> list[PhaseRow]:
    clauses = ["user_id = ?"]
    params: list[int] = [user_id]
    if since_ts is not None:
        clauses.append("end_date >= ?")
        params.append(since_ts)
    if until_ts is not None:
        clauses.append("start_date <= ?")
        params.append(until_ts)
    where = " AND ".join(clauses)
    rows = await (
        await conn.execute(
            f"SELECT id, user_id, phase_name, start_date, end_date, color_hex, notes "
            f"FROM training_phases WHERE {where} ORDER BY start_date ASC",
            tuple(params),
        )
    ).fetchall()
    return [
        PhaseRow(
            id=int(r["id"]),
            user_id=int(r["user_id"]),
            phase_name=r["phase_name"],
            start_date=int(r["start_date"]),
            end_date=int(r["end_date"]),
            color_hex=r["color_hex"],
            notes=r["notes"],
        )
        for r in rows
    ]


async def insert_phase(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    phase_name: str,
    start_date: int,
    end_date: int,
    color_hex: str | None = None,
    notes: str | None = None,
) -> int:
    cur = await conn.execute(
        "INSERT INTO training_phases (user_id, phase_name, start_date, end_date, "
        "color_hex, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, phase_name, start_date, end_date, color_hex, notes),
    )
    await conn.commit()
    return int(cur.lastrowid)  # type: ignore[return-value]
