"""Handler for free-form questions about rep maxes.

Registered BEFORE the log catch-all so that "какой максимум на присед?"
is intercepted as a question, not parsed as a workout log.
"""

from __future__ import annotations

import aiosqlite
from aiogram import F, Router
from aiogram.filters import Filter
from aiogram.types import Message

from pwrbot.db import repo
from pwrbot.services.max_query import MaxQuery, MaxQueryService, try_parse_max_question

router = Router()


class IsMaxQuestion(Filter):
    """Custom aiogram 3 filter: returns False for non-questions (message falls
    through to the next router), injects ``max_query: MaxQuery`` when matched."""

    async def __call__(self, message: Message) -> bool | dict:
        text = message.text or ""
        parsed = try_parse_max_question(text)
        if parsed is None:
            return False
        return {"max_query": parsed}


@router.message(F.text & ~F.text.startswith("/"), IsMaxQuestion())
async def handle_max_question(
    message: Message,
    conn: aiosqlite.Connection,
    max_query: MaxQuery,
    max_query_svc: MaxQueryService,
) -> None:
    if message.from_user is None:
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    reply = await max_query_svc.answer(conn, user_id=uid, query=max_query)
    await message.answer(reply)
