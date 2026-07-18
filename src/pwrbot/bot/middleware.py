"""Middleware: dependency injection (DB, services) into handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from pwrbot.config import YamlConfig
from pwrbot.domain.catalog import Catalog
from pwrbot.services.analyze import AnalyzeService
from pwrbot.services.chart_images import ChartImageService
from pwrbot.services.ingest import IngestService
from pwrbot.services.max_query import MaxQueryService
from pwrbot.services.predict import PredictService
from pwrbot.services.technique import TechniqueAnalysisService


class TelegramAllowlistMiddleware(BaseMiddleware):
    """Stops all Telegram events from users outside the configured allowlist."""

    def __init__(self, *, allowed_telegram_ids: set[int]) -> None:
        self._allowed_telegram_ids = allowed_telegram_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Fail closed: an empty allowlist denies everyone. A missing or blank
        # PWRBOT_ALLOWED_TELEGRAM_IDS must NOT turn this single-user bot into an
        # open one. The production entrypoint also refuses to start with an empty
        # allowlist (see __main__), but the gate is enforced here too so the
        # contract holds no matter how the dispatcher is constructed.
        from_user = getattr(event, "from_user", None)
        if from_user is None and isinstance(event, CallbackQuery):
            from_user = event.from_user
        user_id = getattr(from_user, "id", None)
        if user_id is not None and user_id in self._allowed_telegram_ids:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer("Доступ закрыт.", show_alert=True)
        elif isinstance(event, Message) or hasattr(event, "answer"):
            await event.answer("Доступ к этому боту закрыт.")
        return None


class DIMiddleware(BaseMiddleware):
    """Injects the shared DB connection and services into handler kwargs."""

    def __init__(
        self,
        *,
        conn: aiosqlite.Connection,
        ingest: IngestService,
        analyze: AnalyzeService,
        max_query_svc: MaxQueryService,
        predict_svc: PredictService,
        chart_images: ChartImageService,
        technique_svc: TechniqueAnalysisService,
        yaml_config: YamlConfig,
        catalog: Catalog,
    ) -> None:
        self._conn = conn
        self._ingest = ingest
        self._analyze = analyze
        self._max_query_svc = max_query_svc
        self._predict_svc = predict_svc
        self._chart_images = chart_images
        self._technique_svc = technique_svc
        self._yaml_config = yaml_config
        self._catalog = catalog

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
        data["predict"] = self._predict_svc
        data["chart_images"] = self._chart_images
        data["technique_svc"] = self._technique_svc
        data["yaml_config"] = self._yaml_config
        data["catalog"] = self._catalog
        return await handler(event, data)
