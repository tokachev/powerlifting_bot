"""Tests for body weight tracking: repo CRUD, message parsing, formatting."""

from __future__ import annotations

from datetime import UTC, datetime

import aiosqlite
import pytest

from pwrbot.bot.formatting import format_rm_estimates
from pwrbot.bot.handlers.weight import IsWeightMessage, _parse_weight_kg
from pwrbot.db.connection import bootstrap
from pwrbot.db.repo import (
    get_body_weight_at,
    get_body_weight_history,
    get_latest_body_weight,
    get_or_create_user,
    upsert_body_weight,
)
from pwrbot.rules.one_rm import OneRMEstimate


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


# ── repo tests ─────────────────────────────────────────────────────────


async def test_upsert_and_get_latest(conn: aiosqlite.Connection) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    ts = 1_700_000_000
    await upsert_body_weight(conn, user_id=uid, recorded_at=ts, weight_g=85_000)

    result = await get_latest_body_weight(conn, uid)
    assert result is not None
    weight_g, recorded_at = result
    assert weight_g == 85_000
    assert recorded_at == ts


async def test_upsert_overwrites_same_date(conn: aiosqlite.Connection) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    ts = 1_700_000_000
    await upsert_body_weight(conn, user_id=uid, recorded_at=ts, weight_g=85_000)
    await upsert_body_weight(conn, user_id=uid, recorded_at=ts, weight_g=86_500)

    result = await get_latest_body_weight(conn, uid)
    assert result is not None
    assert result[0] == 86_500


async def test_get_latest_returns_most_recent(conn: aiosqlite.Connection) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    await upsert_body_weight(conn, user_id=uid, recorded_at=1_700_000_000, weight_g=85_000)
    await upsert_body_weight(conn, user_id=uid, recorded_at=1_700_100_000, weight_g=86_000)

    result = await get_latest_body_weight(conn, uid)
    assert result is not None
    assert result[0] == 86_000
    assert result[1] == 1_700_100_000


async def test_get_latest_returns_none_when_empty(conn: aiosqlite.Connection) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    assert await get_latest_body_weight(conn, uid) is None


async def test_get_body_weight_at(conn: aiosqlite.Connection) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    await upsert_body_weight(conn, user_id=uid, recorded_at=1_000, weight_g=80_000)
    await upsert_body_weight(conn, user_id=uid, recorded_at=2_000, weight_g=82_000)
    await upsert_body_weight(conn, user_id=uid, recorded_at=3_000, weight_g=84_000)

    # Exact match
    assert await get_body_weight_at(conn, uid, 2_000) == 82_000
    # Between entries — returns earlier
    assert await get_body_weight_at(conn, uid, 2_500) == 82_000
    # Before any entry
    assert await get_body_weight_at(conn, uid, 500) is None
    # After all entries
    assert await get_body_weight_at(conn, uid, 5_000) == 84_000


async def test_get_body_weight_history(conn: aiosqlite.Connection) -> None:
    uid = await get_or_create_user(conn, telegram_id=42)
    await upsert_body_weight(conn, user_id=uid, recorded_at=1_000, weight_g=80_000)
    await upsert_body_weight(conn, user_id=uid, recorded_at=2_000, weight_g=82_000)
    await upsert_body_weight(conn, user_id=uid, recorded_at=3_000, weight_g=84_000)

    history = await get_body_weight_history(conn, user_id=uid, since_ts=1_000, until_ts=2_000)
    assert len(history) == 2
    assert history[0] == (1_000, 80_000)
    assert history[1] == (2_000, 82_000)


# ── parsing tests ──────────────────────────────────────────────────────


def test_parse_weight_kg_valid() -> None:
    assert _parse_weight_kg("85.5") == 85.5
    assert _parse_weight_kg("86") == 86.0
    assert _parse_weight_kg("85,5") == 85.5
    assert _parse_weight_kg("100") == 100.0


def test_parse_weight_kg_out_of_range() -> None:
    assert _parse_weight_kg("10") is None
    assert _parse_weight_kg("350") is None


def test_parse_weight_kg_invalid() -> None:
    assert _parse_weight_kg("abc") is None


class FakeMessage:
    """Minimal fake for testing IsWeightMessage filter."""

    def __init__(self, text: str) -> None:
        self.text = text


@pytest.fixture
def weight_filter() -> IsWeightMessage:
    return IsWeightMessage()


async def test_filter_weight_input_simple(weight_filter: IsWeightMessage) -> None:
    result = await weight_filter(FakeMessage("вес 85.5"))
    assert isinstance(result, dict)
    assert result["bw_kg"] == 85.5
    assert "bw_date" in result


async def test_filter_weight_input_with_kg(weight_filter: IsWeightMessage) -> None:
    result = await weight_filter(FakeMessage("вес 86 кг"))
    assert isinstance(result, dict)
    assert result["bw_kg"] == 86.0


async def test_filter_weight_input_comma(weight_filter: IsWeightMessage) -> None:
    result = await weight_filter(FakeMessage("вес 85,5"))
    assert isinstance(result, dict)
    assert result["bw_kg"] == 85.5


async def test_filter_weight_input_with_date(weight_filter: IsWeightMessage) -> None:
    result = await weight_filter(FakeMessage("вес 85 вчера"))
    assert isinstance(result, dict)
    assert result["bw_kg"] == 85.0
    yesterday = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    yesterday = yesterday - timedelta(days=1)
    assert result["bw_date"].date() == yesterday.date()


async def test_filter_weight_input_moy_ves(weight_filter: IsWeightMessage) -> None:
    result = await weight_filter(FakeMessage("мой вес 90"))
    assert isinstance(result, dict)
    assert result["bw_kg"] == 90.0


async def test_filter_weight_query(weight_filter: IsWeightMessage) -> None:
    result = await weight_filter(FakeMessage("мой вес"))
    assert isinstance(result, dict)
    assert result.get("bw_query") is True


async def test_filter_weight_query_with_question_mark(weight_filter: IsWeightMessage) -> None:
    result = await weight_filter(FakeMessage("вес?"))
    assert isinstance(result, dict)
    assert result.get("bw_query") is True


async def test_filter_weight_query_kakoy(weight_filter: IsWeightMessage) -> None:
    result = await weight_filter(FakeMessage("какой мой вес"))
    assert isinstance(result, dict)
    assert result.get("bw_query") is True


async def test_filter_non_weight_message(weight_filter: IsWeightMessage) -> None:
    result = await weight_filter(FakeMessage("присед 4x5x100"))
    assert result is False


async def test_filter_out_of_range(weight_filter: IsWeightMessage) -> None:
    result = await weight_filter(FakeMessage("вес 10"))
    assert result is False


# ── formatting tests ───────────────────────────────────────────────────


def test_format_rm_estimates_without_bw() -> None:
    estimates = [
        OneRMEstimate(
            canonical_name="back_squat",
            target_group="squat",
            best_set_weight_kg=140.0,
            best_set_reps=3,
            estimated_1rm_kg=150.0,
        )
    ]
    result = format_rm_estimates(estimates)
    assert result is not None
    assert "~150 кг" in result
    assert "BW" not in result


def test_format_rm_estimates_with_bw() -> None:
    estimates = [
        OneRMEstimate(
            canonical_name="back_squat",
            target_group="squat",
            best_set_weight_kg=140.0,
            best_set_reps=3,
            estimated_1rm_kg=150.0,
        )
    ]
    result = format_rm_estimates(estimates, body_weight_kg=85.0)
    assert result is not None
    assert "~150 кг" in result
    assert "~1.76 BW" in result


def test_format_rm_estimates_bw_none_no_crash() -> None:
    estimates = [
        OneRMEstimate(
            canonical_name="bench_press",
            target_group="bench",
            best_set_weight_kg=100.0,
            best_set_reps=5,
            estimated_1rm_kg=112.0,
        )
    ]
    result = format_rm_estimates(estimates, body_weight_kg=None)
    assert result is not None
    assert "BW" not in result
