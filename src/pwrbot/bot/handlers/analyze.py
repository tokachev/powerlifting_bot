"""/analyze [7|28]."""

from __future__ import annotations

import aiosqlite
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from pwrbot.bot.formatting import format_analysis
from pwrbot.db import repo
from pwrbot.services.analyze import AnalyzeService

router = Router()


@router.message(Command("analyze"))
async def cmd_analyze(
    message: Message,
    command: CommandObject,
    conn: aiosqlite.Connection,
    analyze: AnalyzeService,
) -> None:
    if message.from_user is None:
        return
    window_days = 7
    if command.args:
        try:
            window_days = int(command.args.strip())
        except ValueError:
            await message.answer("Использование: `/analyze [7|28]`")
            return
    if window_days not in (7, 28):
        await message.answer("Окно должно быть 7 или 28 дней.")
        return

    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    await message.bot.send_chat_action(message.chat.id, "typing")
    result = await analyze.analyze(conn, user_id=uid, window_days=window_days)
    await message.answer(format_analysis(result))
