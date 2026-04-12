"""/delete_last and /edit_last.

`/edit_last <text>` is modelled as full-replace: delete the last workout then
re-ingest the new text. Simpler than field-level editing and obvious to the user.
"""

from __future__ import annotations

import aiosqlite
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from pwrbot.bot.formatting import format_ingest_reply
from pwrbot.db import repo
from pwrbot.services.ingest import IngestService

router = Router()


@router.message(Command("delete_last"))
async def cmd_delete_last(message: Message, conn: aiosqlite.Connection) -> None:
    if message.from_user is None:
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    deleted = await repo.delete_last_workout(conn, user_id=uid)
    if deleted is None:
        await message.answer("Удалять нечего — тренировок пока нет.")
        return
    await message.answer(f"Удалил последнюю тренировку (id={deleted}).")


@router.message(Command("edit_last"))
async def cmd_edit_last(
    message: Message,
    command: CommandObject,
    conn: aiosqlite.Connection,
    ingest: IngestService,
) -> None:
    if message.from_user is None:
        return
    new_text = (command.args or "").strip()
    if not new_text:
        await message.answer("Использование: `/edit_last <новый текст тренировки>`")
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    deleted = await repo.delete_last_workout(conn, user_id=uid)
    if deleted is None:
        await message.answer("Нечего редактировать — тренировок пока нет.")
        return
    await message.bot.send_chat_action(message.chat.id, "typing")
    result = await ingest.ingest(conn, user_id=uid, source_text=new_text)
    if result.parse_error:
        await message.answer(
            "Удалил старую, но новую не распарсил. "
            "Попробуй формат `упражнение NxRxW`."
        )
        return
    await message.answer(
        "Заменил последнюю тренировку.\n\n"
        + format_ingest_reply(
            result.payload, result.analysis, result.rm_estimates,
            result.body_weight_kg, result.new_prs,
        )
    )
