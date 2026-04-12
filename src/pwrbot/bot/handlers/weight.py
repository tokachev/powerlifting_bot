"""Free-text body-weight input and query handler.

Intercepts messages like ``вес 85.5``, ``вес 86 кг вчера``, ``мой вес``.
Must be registered BEFORE the log catch-all router.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import aiosqlite
from aiogram import F, Router
from aiogram.filters import Filter
from aiogram.types import Message

from pwrbot.db import repo
from pwrbot.parsing.normalize import kg_to_g
from pwrbot.parsing.preprocess import parse_workout_date

router = Router()

# ── regex patterns ────────────────────────────────────────────────────────

# "вес 85.5", "мой вес 86 кг", "вес 85,5 кг"
_RE_WEIGHT_INPUT = re.compile(
    r"^\s*(?:мой\s+)?вес\s+(?P<kg>\d+(?:[.,]\d+)?)\s*(?:кг|kg)?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)

# "мой вес", "вес?", "какой мой вес"
_RE_WEIGHT_QUERY = re.compile(
    r"^\s*(?:какой\s+)?(?:мой\s+)?вес\s*\??\s*$",
    re.IGNORECASE,
)


def _parse_weight_kg(raw: str) -> float | None:
    """Parse a weight string, accepting both '.' and ',' as decimal separator."""
    raw = raw.replace(",", ".")
    try:
        val = float(raw)
    except ValueError:
        return None
    if val < 30 or val > 300:
        return None
    return val


# ── aiogram filter ────────────────────────────────────────────────────────


class IsWeightMessage(Filter):
    """Returns False for non-weight messages.

    On match injects one of:
    - ``{"bw_kg": float, "bw_date": datetime}`` — weight input
    - ``{"bw_query": True}`` — query for latest weight
    """

    async def __call__(self, message: Message) -> bool | dict:
        text = message.text or ""

        # Try input first (has a number)
        m = _RE_WEIGHT_INPUT.match(text)
        if m:
            kg = _parse_weight_kg(m.group("kg"))
            if kg is None:
                return False
            rest = m.group("rest").strip()
            now = datetime.now(UTC)
            date = parse_workout_date(rest, now) if rest else None
            if date is None:
                date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return {"bw_kg": kg, "bw_date": date}

        # Try query (no number, just "вес" / "мой вес")
        if _RE_WEIGHT_QUERY.match(text):
            return {"bw_query": True}

        return False


# ── handlers ──────────────────────────────────────────────────────────────


def _fmt_weight(kg: float) -> str:
    if kg == int(kg):
        return f"{int(kg)}"
    return f"{kg:.1f}"


def _fmt_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%d.%m.%Y")


@router.message(F.text & ~F.text.startswith("/"), IsWeightMessage())
async def handle_weight(
    message: Message,
    conn: aiosqlite.Connection,
    bw_kg: float | None = None,
    bw_date: datetime | None = None,
    bw_query: bool = False,
) -> None:
    if message.from_user is None:
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)

    if bw_query:
        latest = await repo.get_latest_body_weight(conn, uid)
        if latest is None:
            await message.answer("Вес ещё не записан.")
        else:
            weight_g, recorded_at = latest
            await message.answer(
                f"Твой последний вес: {_fmt_weight(weight_g / 1000)} кг "
                f"({_fmt_date(recorded_at)})"
            )
        return

    # Weight input
    recorded_at = int(bw_date.timestamp())
    weight_g = kg_to_g(bw_kg)
    await repo.upsert_body_weight(
        conn, user_id=uid, recorded_at=recorded_at, weight_g=weight_g,
    )
    await message.answer(
        f"Записал вес {_fmt_weight(bw_kg)} кг на {_fmt_date(recorded_at)}"
    )
