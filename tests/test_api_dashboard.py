"""Integration tests for the FastAPI dashboard endpoints."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from pwrbot.api.main import create_app
from pwrbot.db import repo
from pwrbot.db.repo import ExerciseRow, SetRow
from pwrbot.domain.catalog import load_catalog
from tests.conftest import REPO_ROOT


def _ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


def _ex(canonical_name, movement_pattern, sets, position=0):
    return ExerciseRow(
        position=position,
        raw_name=canonical_name,
        canonical_name=canonical_name,
        movement_pattern=movement_pattern,
        sets=[
            SetRow(reps=r, weight_g=w * 1000, rpe=None, is_warmup=warmup, set_index=i)
            for i, (r, w, warmup) in enumerate(sets)
        ],
    )


@pytest.fixture
async def client(conn):
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    app = create_app(catalog, lifespan=False)
    app.state.conn = conn
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def test_health(client) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_catalog_endpoint_includes_new_fields(client) -> None:
    r = await client.get("/api/catalog")
    assert r.status_code == 200
    items = r.json()
    by_name = {e["canonical_name"]: e for e in items}
    bs = by_name["back_squat"]
    assert bs["target_group"] == "squat"
    assert bs["muscle_group"] == "legs"
    assert bs["movement_pattern"] == "squat"
    bp = by_name["bench_press"]
    assert bp["target_group"] == "bench"
    assert bp["muscle_group"] == "chest"
    # An exercise without target_group
    bicep = by_name["bicep_curl"]
    assert bicep["target_group"] is None
    assert bicep["muscle_group"] == "arms"


async def test_users_endpoint(client, conn) -> None:
    await repo.get_or_create_user(conn, telegram_id=42, display_name="alice")
    r = await client.get("/api/users")
    assert r.status_code == 200
    users = r.json()
    assert len(users) == 1
    assert users[0]["telegram_id"] == 42
    assert users[0]["display_name"] == "alice"


async def test_dashboard_unknown_user_404(client) -> None:
    today = date(2026, 4, 1)
    r = await client.get(
        "/api/dashboard",
        params={"user_id": 999, "since": today.isoformat(), "until": today.isoformat()},
    )
    assert r.status_code == 404


async def test_dashboard_basic_aggregation(client, conn) -> None:
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    today = date(2026, 4, 1)
    await repo.insert_workout(
        conn,
        user_id=uid,
        performed_at=_ts(today) + 10 * 3600,
        source_text="test",
        exercises=[
            _ex("back_squat", "squat", [(5, 100, False), (5, 100, False)]),
            _ex("bench_press", "push", [(5, 80, False)], position=1),
        ],
    )
    r = await client.get(
        "/api/dashboard",
        params={
            "user_id": uid,
            "since": today.isoformat(),
            "until": today.isoformat(),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == [today.isoformat()]
    assert body["kpsh_by_bucket"]["squat"] == [10]
    assert body["kpsh_by_bucket"]["bench"] == [5]
    assert body["kpsh_by_bucket"]["deadlift"] == [0]
    assert body["kpsh_by_bucket"]["other"] == [0]
    assert body["total_kpsh"] == 15
    assert body["total_workouts"] == 1
    assert body["filters"]["target_only"] is False
    assert body["filters"]["since"] == today.isoformat()


async def test_dashboard_default_window_is_28d(client, conn) -> None:
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    r = await client.get("/api/dashboard", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    # Default window is the trailing 28 days inclusive → 28 entries
    assert len(body["days"]) == 28
    today = datetime.now(UTC).date()
    assert body["days"][-1] == today.isoformat()
    assert body["days"][0] == (today - timedelta(days=27)).isoformat()


async def test_dashboard_target_only_filter(client, conn) -> None:
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    today = date(2026, 4, 1)
    await repo.insert_workout(
        conn,
        user_id=uid,
        performed_at=_ts(today) + 10 * 3600,
        source_text="test",
        exercises=[
            _ex("bench_press", "push", [(5, 100, False)]),
            _ex("bicep_curl", "accessory", [(10, 15, False)], position=1),
        ],
    )
    r = await client.get(
        "/api/dashboard",
        params={
            "user_id": uid,
            "since": today.isoformat(),
            "until": today.isoformat(),
            "target_only": "true",
        },
    )
    body = r.json()
    assert body["kpsh_by_bucket"]["bench"] == [5]
    assert body["kpsh_by_bucket"]["other"] == [0]
    assert body["total_kpsh"] == 5


async def test_dashboard_invalid_filter_400(client, conn) -> None:
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    r = await client.get(
        "/api/dashboard",
        params={"user_id": uid, "muscle_groups": ["wings"]},
    )
    assert r.status_code == 400
    assert "muscle_group" in r.json()["detail"]


async def test_dashboard_since_after_until_400(client, conn) -> None:
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    r = await client.get(
        "/api/dashboard",
        params={"user_id": uid, "since": "2026-04-10", "until": "2026-04-01"},
    )
    assert r.status_code == 400


async def test_dashboard_repeated_query_params(client, conn) -> None:
    """Multi-value filters arrive as repeated query params (?muscle_groups=a&muscle_groups=b)."""
    uid = await repo.get_or_create_user(conn, telegram_id=1)
    today = date(2026, 4, 1)
    await repo.insert_workout(
        conn,
        user_id=uid,
        performed_at=_ts(today) + 10 * 3600,
        source_text="test",
        exercises=[
            _ex("back_squat", "squat", [(5, 100, False)]),
            _ex("bench_press", "push", [(5, 80, False)], position=1),
            _ex("bicep_curl", "accessory", [(10, 15, False)], position=2),
        ],
    )
    r = await client.get(
        "/api/dashboard",
        params=[
            ("user_id", str(uid)),
            ("since", today.isoformat()),
            ("until", today.isoformat()),
            ("muscle_groups", "legs"),
            ("muscle_groups", "chest"),
        ],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kpsh_by_bucket"]["squat"] == [5]
    assert body["kpsh_by_bucket"]["bench"] == [5]
    # arms (bicep) excluded
    assert body["total_kpsh"] == 10
    assert body["filters"]["muscle_groups"] == ["legs", "chest"]
