"""/log command and free-text ingestion.

If the parser returned exercises that couldn't be canonicalized, control is
handed off to the clarify FSM — the user picks a canonical key from an inline
keyboard and the workout is persisted only once all exercises are resolved.
"""

from __future__ import annotations

import aiosqlite
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from pwrbot.bot.formatting import format_ingest_reply
from pwrbot.bot.handlers.clarify import start_clarification
from pwrbot.db import repo
from pwrbot.services.ingest import IngestService

router = Router()


async def _ingest_text(
    message: Message,
    text: str,
    conn: aiosqlite.Connection,
    ingest: IngestService,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    if not text.strip():
        await message.answer("Пришли текст тренировки, например: `присед 4x5x100`")
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)

    # typing indicator while LLM runs
    await message.bot.send_chat_action(message.chat.id, "typing")
    result = await ingest.ingest(conn, user_id=uid, source_text=text)

    if result.parse_error:
        await message.answer(
            "Не смог распарсить тренировку. Попробуй формат "
            "`упражнение NxRxW`, например `присед 4x5x100`."
        )
        return

    if result.pending is not None:
        await start_clarification(message, state, result.pending)
        return

    await message.answer(
        format_ingest_reply(
            result.payload, result.analysis, result.rm_estimates, result.body_weight_kg
        )
    )


@router.message(Command("log"))
async def cmd_log(
    message: Message,
    conn: aiosqlite.Connection,
    ingest: IngestService,
    state: FSMContext,
) -> None:
    text = (message.text or message.caption or "").partition(" ")[2]
    await _ingest_text(message, text, conn, ingest, state)


@router.message(F.text & ~F.text.startswith("/"))
async def plain_text_log(
    message: Message,
    conn: aiosqlite.Connection,
    ingest: IngestService,
    state: FSMContext,
) -> None:
    await _ingest_text(message, message.text or "", conn, ingest, state)
