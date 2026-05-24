"""Telegram handlers for dashboard chart images."""

from __future__ import annotations

import aiosqlite
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from pwrbot.services.chart_images import (
    ChartImageService,
    ChartRenderRequest,
    get_chart_definition,
    list_chart_definitions,
)

router = Router()

_CHART_ALIASES = {
    "bodyweight": "bodyweight-trend",
    "bw": "bodyweight-trend",
    "вес": "bodyweight-trend",
}

_LIFT_ALIASES = {
    "squat": "squat",
    "присед": "squat",
    "bench": "bench",
    "жим": "bench",
    "deadlift": "deadlift",
    "тяга": "deadlift",
    "становая": "deadlift",
}


def _charts_help() -> str:
    lines = ["Доступные графики:"]
    for chart in list_chart_definitions():
        suffix = " <squat|bench|deadlift>" if chart.requires_lift else ""
        lines.append(f"/chart {chart.id}{suffix} [weeks] — {chart.title}")
    return "\n".join(lines)


async def _user_id_for_message(conn: aiosqlite.Connection, message: Message) -> int | None:
    if message.from_user is None:
        return None
    async with conn.execute(
        "SELECT id FROM users WHERE telegram_id = ?", (message.from_user.id,)
    ) as cur:
        row = await cur.fetchone()
    return int(row["id"]) if row is not None else None


def _parse_chart_request(text: str, *, user_id: int) -> ChartRenderRequest:
    parts = text.split()[1:]
    if not parts:
        raise ValueError(_charts_help())
    chart_id = _CHART_ALIASES.get(parts[0].lower(), parts[0])
    definition = get_chart_definition(chart_id)
    lift: str | None = None
    weeks = 14
    for raw in parts[1:]:
        token = raw.strip().lower()
        if token in _LIFT_ALIASES:
            lift = _LIFT_ALIASES[token]
        elif token.isdigit():
            weeks = int(token)
            if weeks < 4 or weeks > 52:
                raise ValueError("weeks must be between 4 and 52")
        else:
            raise ValueError(f"Не понимаю параметр: {raw}")
    if definition.requires_lift and lift is None:
        lift = "squat"
    return ChartRenderRequest(chart_id=chart_id, user_id=user_id, weeks=weeks, lift=lift)


@router.message(Command("charts"))
async def cmd_charts(message: Message) -> None:
    await message.answer(_charts_help())


@router.message(Command("chart"))
async def cmd_chart(
    message: Message,
    conn: aiosqlite.Connection,
    chart_images: ChartImageService,
) -> None:
    user_id = await _user_id_for_message(conn, message)
    if user_id is None:
        await message.answer("Сначала напиши /start, чтобы я связал Telegram с дневником.")
        return
    try:
        request = _parse_chart_request(message.text or "", user_id=user_id)
    except ValueError as exc:
        text = str(exc)
        if text.startswith("Unknown chart"):
            text = "Неизвестный график.\n\n" + _charts_help()
        await message.answer(text)
        return

    definition = get_chart_definition(request.chart_id)
    try:
        png = await chart_images.render(request)
    except Exception:
        await message.answer("Не смог сгенерировать график: dashboard недоступен или вернул ошибку.")
        return
    await message.answer_photo(
        BufferedInputFile(png, filename=f"{request.chart_id}.png"),
        caption=f"{definition.title} ({definition.id}) · {request.weeks} нед.",
    )
