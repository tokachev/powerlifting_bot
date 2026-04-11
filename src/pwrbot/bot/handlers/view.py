"""/today, /lastworkout, /week — read-only views, no LLM."""

from __future__ import annotations

import time

import aiosqlite
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from pwrbot.bot.formatting import format_week_summary, format_workout_row
from pwrbot.db import repo

router = Router()

DAY_S = 86_400


@router.message(Command("today"))
async def cmd_today(message: Message, conn: aiosqlite.Connection) -> None:
    if message.from_user is None:
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    now_ts = int(time.time())
    today_start = now_ts - (now_ts % DAY_S)
    workouts = await repo.get_workouts_in_window(
        conn, user_id=uid, since_ts=today_start, until_ts=now_ts
    )
    if not workouts:
        await message.answer("Сегодня тренировок нет.")
        return
    blocks = [format_workout_row(w) for w in workouts]
    await message.answer("\n\n".join(blocks))


@router.message(Command("lastworkout"))
async def cmd_lastworkout(message: Message, conn: aiosqlite.Connection) -> None:
    if message.from_user is None:
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    w = await repo.get_last_workout(conn, user_id=uid)
    if w is None:
        await message.answer("Тренировок ещё нет.")
        return
    await message.answer(format_workout_row(w))


@router.message(Command("week"))
async def cmd_week(message: Message, conn: aiosqlite.Connection) -> None:
    if message.from_user is None:
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    now_ts = int(time.time())
    workouts = await repo.get_workouts_in_window(
        conn, user_id=uid, since_ts=now_ts - 7 * DAY_S, until_ts=now_ts
    )
    await message.answer(format_week_summary(workouts))
