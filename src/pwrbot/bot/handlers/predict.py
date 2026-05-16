"""/predict — Codex план следующей тренировки."""

from __future__ import annotations

import aiosqlite
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from pwrbot.db import repo
from pwrbot.services.predict import PredictService

_TG_MSG_LIMIT = 4096

router = Router()


def _split_text(text: str, limit: int = _TG_MSG_LIMIT) -> list[str]:
    text = text.strip() or "Не смог построить прогноз через Codex. Попробуй ещё раз позже."
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip()
    return parts


@router.message(Command("predict"))
async def cmd_predict(
    message: Message,
    conn: aiosqlite.Connection,
    predict: PredictService,
) -> None:
    if message.from_user is None:
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    await message.bot.send_chat_action(message.chat.id, "typing")
    result = await predict.predict_next_workout(conn, user_id=uid)
    for chunk in _split_text(result.text):
        await message.answer(chunk)
