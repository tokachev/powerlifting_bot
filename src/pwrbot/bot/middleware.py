"""Middleware: dependency injection (DB, services) into handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from pwrbot.services.analyze import AnalyzeService
from pwrbot.services.ingest import IngestService
from pwrbot.services.max_query import MaxQueryService


class DIMiddleware(BaseMiddleware):
    """Injects the shared DB connection and services into handler kwargs."""

    def __init__(
        self,
        *,
        conn: aiosqlite.Connection,
        ingest: IngestService,
        analyze: AnalyzeService,
        max_query_svc: MaxQueryService,
    ) -> None:
        self._conn = conn
        self._ingest = ingest
        self._analyze = analyze
        self._max_query_svc = max_query_svc

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["conn"] = self._conn
        data["ingest"] = self._ingest
        data["analyze"] = self._analyze
        data["max_query_svc"] = self._max_query_svc
        return await handler(event, data)
