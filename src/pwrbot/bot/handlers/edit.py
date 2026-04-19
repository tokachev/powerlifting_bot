"""/delete_last, /edit_last, /add.

`/edit_last <text>` is modelled as full-replace: delete the last workout then
re-ingest the new text. Simpler than field-level editing and obvious to the user.

`/add <text>` parses the text the same way as a normal log message but appends
the resulting exercises to the most recent workout — for cases like "забыл одно
упражнение и хочу добавить".
"""

from __future__ import annotations

import aiosqlite
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from pwrbot.bot.formatting import format_ingest_reply
from pwrbot.bot.handlers.clarify import start_clarification
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


@router.message(Command("add"))
async def cmd_add(
    message: Message,
    command: CommandObject,
    conn: aiosqlite.Connection,
    ingest: IngestService,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    text = (command.args or "").strip()
    if not text:
        await message.answer(
            "Использование: `/add <текст>` — дописать упражнения к последней тренировке."
        )
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    await message.bot.send_chat_action(message.chat.id, "typing")
    result = await ingest.append_to_last(conn, user_id=uid, source_text=text)

    if result.parse_error:
        # Distinguish "no workout to append to" from a real parse failure so the
        # user gets an actionable message instead of a generic format hint.
        if "Нет тренировок" in result.parse_error:
            await message.answer(result.parse_error)
        else:
            await message.answer(
                "Не смог распарсить дополнение. Попробуй формат "
                "`упражнение NxRxW`, например `подтягивания 3x8`."
            )
        return

    if result.pending is not None:
        await start_clarification(message, state, result.pending)
        return

    await message.answer(
        "Дописал к последней тренировке.\n\n"
        + format_ingest_reply(
            result.payload, result.analysis, result.rm_estimates,
            result.body_weight_kg, result.new_prs,
        )
    )
