"""/start and /help handlers."""

from __future__ import annotations

import aiosqlite
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from pwrbot.db import repo

router = Router()

HELP_TEXT = """\
Доступные команды:
/start — регистрация
/help — эта справка
/log <текст> — залогировать тренировку (можно просто отправить текст без команды)
/today — сегодняшние тренировки
/lastworkout — последняя тренировка
/week — сводка за 7 дней
/analyze [7|28] — полный анализ за окно (по умолчанию 7)
/delete_last — удалить последнюю тренировку
/edit_last <текст> — заменить последнюю тренировку
/1rm [упражнение] — расчётный 1RM (без аргумента — SBD)
/stats — краткая статистика за 7 дней
/prs — последние рекорды
/volume — hard-сеты за 7 дней vs ориентиры

Вес тела:
  «вес 85.5» — записать вес (можно добавить дату: «вес 85 12.03»)
  «мой вес» — показать последний записанный вес

Формат ввода:
  присед 4x5x100 rpe8
  жим 5 подходов по 8 80кг
  становая 3×3×140, разминка 60×10

Анализ техники:
  Отправь видео (или кружок) — бот проанализирует технику.
  Можно добавить подпись с названием упражнения (напр. «присед»).

После каждого /log бот автоматически прогоняет 7-дневный анализ.
"""


@router.message(CommandStart())
async def cmd_start(message: Message, conn: aiosqlite.Connection) -> None:
    if message.from_user is None:
        return
    await repo.get_or_create_user(
        conn,
        telegram_id=message.from_user.id,
        display_name=message.from_user.full_name,
    )
    await message.answer(
        "Привет! Я твой локальный тренировочный дневник.\n\n" + HELP_TEXT
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)
