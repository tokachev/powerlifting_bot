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
from pwrbot.bot.handlers import max_query as h_max_query
from pwrbot.bot.handlers import stats as h_stats
from pwrbot.bot.handlers import video as h_video
from pwrbot.bot.handlers import view as h_view
from pwrbot.bot.handlers import weight as h_weight
from pwrbot.bot.middleware import DIMiddleware
from pwrbot.config import YamlConfig
from pwrbot.domain.catalog import Catalog
from pwrbot.services.analyze import AnalyzeService
from pwrbot.services.ingest import IngestService
from pwrbot.services.max_query import MaxQueryService
from pwrbot.services.technique import TechniqueAnalysisService


def build_dispatcher(
    *,
    conn: aiosqlite.Connection,
    ingest: IngestService,
    analyze: AnalyzeService,
    max_query_svc: MaxQueryService,
    technique_svc: TechniqueAnalysisService,
    yaml_config: YamlConfig,
    catalog: Catalog,
) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    di = DIMiddleware(
        conn=conn, ingest=ingest, analyze=analyze, max_query_svc=max_query_svc,
        technique_svc=technique_svc, yaml_config=yaml_config, catalog=catalog,
    )
    dp.message.middleware(di)
    dp.callback_query.middleware(di)

    dp.include_router(h_basic.router)
    dp.include_router(h_view.router)
    dp.include_router(h_analyze.router)
    dp.include_router(h_edit.router)
    dp.include_router(h_stats.router)        # /1rm, /stats, /prs, /volume commands
    dp.include_router(h_clarify.router)     # FSM state guard — must come before log
    dp.include_router(h_weight.router)      # body weight input — must come before log
    dp.include_router(h_max_query.router)   # max question — must come before log
    dp.include_router(h_video.router)       # video technique analysis
    dp.include_router(h_log.router)         # plain-text catch-all is last
    return dp


def build_bot(token: str) -> Bot:
    return Bot(token=token)
