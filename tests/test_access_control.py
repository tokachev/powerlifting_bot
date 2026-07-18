from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient, BasicAuth

from pwrbot.api.main import build_production_app, create_app
from pwrbot.bot.middleware import TelegramAllowlistMiddleware
from pwrbot.db import repo
from pwrbot.domain.catalog import load_catalog
from tests.conftest import REPO_ROOT


@pytest.fixture
async def authed_client(conn):
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    app = create_app(
        catalog,
        lifespan=False,
        dashboard_auth=("artem", "secret"),
        allowed_telegram_ids={417753103},
    )
    app.state.conn = conn
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def test_production_app_loads_dashboard_security_from_dotenv(
    conn, monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "TELEGRAM_TOKEN=123:abc",
                "PWRBOT_ALLOWED_TELEGRAM_IDS=417753103",
                "PWRBOT_DASHBOARD_USERNAME=dotenv-user",
                "PWRBOT_DASHBOARD_PASSWORD=dotenv-pass",
                f"CONFIG_PATH={REPO_ROOT / 'config' / 'settings.yaml'}",
                f"EXERCISES_PATH={REPO_ROOT / 'config' / 'exercises.yaml'}",
            ]
        ),
        encoding="utf-8",
    )
    app = build_production_app()
    app.state.conn = conn
    await repo.get_or_create_user(conn, telegram_id=417753103, display_name="Artem")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        unauthenticated = await ac.get("/api/users")
        authenticated = await ac.get(
            "/api/users", auth=BasicAuth("dotenv-user", "dotenv-pass")
        )

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200
    assert authenticated.json() == [
        {"id": 1, "telegram_id": None, "display_name": "Artem"}
    ]


async def test_api_requires_basic_auth(authed_client) -> None:
    r = await authed_client.get("/api/users")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Basic"


async def test_api_rejects_wrong_basic_auth(authed_client) -> None:
    r = await authed_client.get("/api/users", auth=BasicAuth("artem", "wrong"))
    assert r.status_code == 401


async def test_api_rejects_malformed_basic_auth_without_500(authed_client) -> None:
    r = await authed_client.get(
        "/api/users", headers={"Authorization": "Basic not-valid-base64"}
    )
    assert r.status_code == 401


async def test_users_endpoint_filters_allowlisted_users_and_redacts_telegram_id(
    authed_client, conn
) -> None:
    await repo.get_or_create_user(conn, telegram_id=417753103, display_name="Artem")
    await repo.get_or_create_user(conn, telegram_id=123456789, display_name="Other")

    r = await authed_client.get("/api/users", auth=BasicAuth("artem", "secret"))

    assert r.status_code == 200
    assert r.json() == [{"id": 1, "telegram_id": None, "display_name": "Artem"}]


async def test_api_forbids_non_allowlisted_user_id(authed_client, conn) -> None:
    blocked_uid = await repo.get_or_create_user(
        conn, telegram_id=123456789, display_name="Other"
    )

    r = await authed_client.get(
        "/api/dashboard",
        params={"user_id": blocked_uid},
        auth=BasicAuth("artem", "secret"),
    )

    assert r.status_code == 403


async def test_api_forbids_unknown_user_id_in_locked_down_mode(authed_client) -> None:
    r = await authed_client.get(
        "/api/dashboard",
        params={"user_id": 999},
        auth=BasicAuth("artem", "secret"),
    )

    assert r.status_code == 403


async def test_powerlifting_api_forbids_non_allowlisted_user_id(
    authed_client, conn
) -> None:
    blocked_uid = await repo.get_or_create_user(
        conn, telegram_id=123456789, display_name="Other"
    )

    r = await authed_client.get(
        "/api/pl/overview",
        params={"user_id": blocked_uid},
        auth=BasicAuth("artem", "secret"),
    )

    assert r.status_code == 403


async def test_powerlifting_write_api_forbids_non_allowlisted_user_id(
    authed_client, conn
) -> None:
    blocked_uid = await repo.get_or_create_user(
        conn, telegram_id=123456789, display_name="Other"
    )

    r = await authed_client.post(
        "/api/pl/bodyweight",
        params={"user_id": blocked_uid},
        json={"recorded_date": "2026-04-01", "weight_kg": 100},
        auth=BasicAuth("artem", "secret"),
    )

    assert r.status_code == 403


async def test_api_allows_allowlisted_user_id(authed_client, conn) -> None:
    allowed_uid = await repo.get_or_create_user(
        conn, telegram_id=417753103, display_name="Artem"
    )

    r = await authed_client.get(
        "/api/dashboard",
        params={"user_id": allowed_uid},
        auth=BasicAuth("artem", "secret"),
    )

    assert r.status_code == 200


async def test_telegram_allowlist_blocks_unknown_user() -> None:
    middleware = TelegramAllowlistMiddleware(allowed_telegram_ids={417753103})
    handler = AsyncMock()
    event = SimpleNamespace(from_user=SimpleNamespace(id=123456789), answer=AsyncMock())

    result = await middleware(handler, event, {})

    assert result is None
    handler.assert_not_awaited()
    event.answer.assert_awaited_once()


async def test_telegram_allowlist_allows_owner() -> None:
    middleware = TelegramAllowlistMiddleware(allowed_telegram_ids={417753103})
    handler = AsyncMock(return_value="ok")
    event = SimpleNamespace(from_user=SimpleNamespace(id=417753103), answer=AsyncMock())

    result = await middleware(handler, event, {})

    assert result == "ok"
    handler.assert_awaited_once()
    event.answer.assert_not_awaited()


async def test_telegram_allowlist_empty_denies_everyone() -> None:
    # Fail closed: an empty allowlist must NOT open the bot to the world.
    middleware = TelegramAllowlistMiddleware(allowed_telegram_ids=set())
    handler = AsyncMock()
    event = SimpleNamespace(from_user=SimpleNamespace(id=417753103), answer=AsyncMock())

    result = await middleware(handler, event, {})

    assert result is None
    handler.assert_not_awaited()
    event.answer.assert_awaited_once()
