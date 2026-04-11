"""Middleware: dependency injection (DB, services) into handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from pwrbot.services.analyze import AnalyzeService
from pwrbot.services.ingest import IngestService


class DIMiddleware(BaseMiddleware):
    """Injects the shared DB connection and services into handler kwargs."""

    def __init__(
        self,
        *,
        conn: aiosqlite.Connection,
        ingest: IngestService,
        analyze: AnalyzeService,
    ) -> None:
        self._conn = conn
        self._ingest = ingest
        self._analyze = analyze

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["conn"] = self._conn
        data["ingest"] = self._ingest
        data["analyze"] = self._analyze
        return await handler(event, data)
