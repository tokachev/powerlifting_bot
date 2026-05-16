"""Smoke tests for /api/pl endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from pwrbot.api.main import create_app
from pwrbot.db import repo
from pwrbot.db.repo import ExerciseRow, SetRow
from pwrbot.domain.catalog import load_catalog
from tests.conftest import REPO_ROOT


@pytest.fixture
async def client(conn, yaml_config):
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    app = create_app(catalog, yaml_config=yaml_config, lifespan=False)
    app.state.conn = conn
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def user_id(conn) -> int:
    return await repo.get_or_create_user(conn, telegram_id=12345, display_name="test")


async def test_overview_empty_user(client, user_id):
    r = await client.get(f"/api/pl/overview?user_id={user_id}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kpi"]["total_kg"] == 0.0
    assert len(data["big3"]) == 3
    assert data["next_meet"] is None


async def test_overview_calendar_includes_workouts_older_than_weeks(
    client, conn, user_id
):
    # Default `weeks=14` would otherwise drop the first 2 weeks of the fixed
    # 16-week heatmap. Insert a workout 15 weeks ago and verify it shows up.
    today = datetime.now(UTC).date()
    fifteen_weeks_ago = today - timedelta(weeks=15)
    performed_at = int(
        datetime(
            fifteen_weeks_ago.year,
            fifteen_weeks_ago.month,
            fifteen_weeks_ago.day,
            tzinfo=UTC,
        ).timestamp()
    )
    await repo.insert_workout(
        conn,
        user_id=user_id,
        performed_at=performed_at,
        source_text="back squat 5x100",
        exercises=[
            ExerciseRow(
                position=0,
                raw_name="присед",
                canonical_name="back_squat",
                movement_pattern="squat",
                sets=[SetRow(reps=5, weight_g=100_000, rpe=None, is_warmup=False, set_index=0)],
            ),
        ],
    )

    r = await client.get(f"/api/pl/overview?user_id={user_id}")
    assert r.status_code == 200, r.text
    calendar = r.json()["calendar"]
    assert len(calendar) == 112
    iso = fifteen_weeks_ago.isoformat()
    cell = next(c for c in calendar if c["date"] == iso)
    assert cell["tonnage_kg"] == 500.0
    assert cell["max_squat_kg"] == 100.0
    assert cell["intensity"] == 4  # only nonzero day → it is the peak


async def test_lift_detail(client, user_id):
    r = await client.get(f"/api/pl/lift/squat?user_id={user_id}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["lift"] == "squat"
    assert len(data["rep_max"]) == 6


async def test_lift_detail_invalid_lift(client, user_id):
    r = await client.get(f"/api/pl/lift/invalid?user_id={user_id}")
    assert r.status_code == 400


async def test_history_empty(client, user_id):
    r = await client.get(f"/api/pl/history?user_id={user_id}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kpi"]["total_meets"] == 0
    assert data["meets"] == []


async def test_create_meet_and_fetch_history(client, user_id):
    body = {
        "meet_date": "2026-03-15",
        "name": "Regional Championship",
        "category": "83kg",
        "federation": "IPF",
        "bodyweight_kg": 82.5,
        "squat_kg": 230,
        "bench_kg": 150,
        "deadlift_kg": 260,
        "place": 2,
        "is_gym_meet": False,
        "is_female": False,
    }
    r = await client.post(f"/api/pl/meets?user_id={user_id}", json=body)
    assert r.status_code == 200, r.text

    r2 = await client.get(f"/api/pl/history?user_id={user_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert data["kpi"]["total_meets"] == 1
    assert data["kpi"]["best_total_kg"] == 640.0
    assert data["meets"][0]["wilks"] is not None
    assert data["meets"][0]["place"] == 2


async def test_next_meet_upsert(client, user_id):
    body = {
        "meet_date": "2026-06-01",
        "name": "Summer Classic",
        "target_squat_kg": 250,
        "target_bench_kg": 160,
        "target_deadlift_kg": 280,
        "attempts_kg": {
            "squat": [240, 250, 260],
            "bench": [150, 160, 165],
            "deadlift": [270, 280, 290],
        },
    }
    r = await client.put(f"/api/pl/next-meet?user_id={user_id}", json=body)
    assert r.status_code == 200

    r2 = await client.get(f"/api/pl/overview?user_id={user_id}")
    data = r2.json()
    assert data["next_meet"]["name"] == "Summer Classic"
    assert data["next_meet"]["target_total_kg"] == 690.0
    assert data["next_meet"]["attempts_kg"]["squat"] == [240.0, 250.0, 260.0]


async def test_create_recovery_and_niggle(client, user_id):
    recorded_date = datetime.now(UTC).date().isoformat()
    r = await client.post(
        f"/api/pl/recovery?user_id={user_id}",
        json={
            "recorded_date": recorded_date,
            "sleep_hours": 7.5,
            "hrv_ms": 55,
            "rhr_bpm": 48,
            "recovery_pct": 82,
        },
    )
    assert r.status_code == 200

    r2 = await client.post(
        f"/api/pl/niggles?user_id={user_id}",
        json={
            "recorded_date": recorded_date,
            "body_area": "low_back",
            "severity": "warn",
            "note": "tight after deadlift",
        },
    )
    assert r2.status_code == 200

    r3 = await client.get(f"/api/pl/overview?user_id={user_id}")
    data = r3.json()
    assert data["readiness"]["latest_recovery_pct"] == 82
    assert len(data["niggles"]) == 1
    assert data["niggles"][0]["body_area"] == "low_back"
