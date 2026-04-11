"""Bot/Dispatcher factory and router wiring."""

from __future__ import annotations

import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from pwrbot.bot.handlers import analyze as h_analyze
from pwrbot.bot.handlers import basic as h_basic
from pwrbot.bot.handlers import clarify as h_clarify
from pwrbot.bot.handlers import edit as h_edit
from pwrbot.bot.handlers import log as h_log
from pwrbot.bot.handlers import view as h_view
from pwrbot.bot.middleware import DIMiddleware
from pwrbot.services.analyze import AnalyzeService
from pwrbot.services.ingest import IngestService


def build_dispatcher(
    *,
    conn: aiosqlite.Connection,
    ingest: IngestService,
    analyze: AnalyzeService,
) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    di = DIMiddleware(conn=conn, ingest=ingest, analyze=analyze)
    dp.message.middleware(di)
    dp.callback_query.middleware(di)

    dp.include_router(h_basic.router)
    dp.include_router(h_view.router)
    dp.include_router(h_analyze.router)
    dp.include_router(h_edit.router)
    dp.include_router(h_clarify.router)   # FSM state guard — must come before log
    dp.include_router(h_log.router)       # plain-text catch-all is last
    return dp


def build_bot(token: str) -> Bot:
    return Bot(token=token)
