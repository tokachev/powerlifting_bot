"""Analyze service: load window → run rules engine → LLM explain → save snapshot."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import aiosqlite

from pwrbot.config import YamlConfig
from pwrbot.db import repo
from pwrbot.logging_setup import get_logger
from pwrbot.parsing.llm_parser import LLMParser
from pwrbot.rules import engine

log = get_logger(__name__)


@dataclass(slots=True)
class AnalyzeResult:
    window_days: int
    metrics: dict[str, Any]
    flags: list[dict[str, Any]]
    explanation: str | None
    snapshot_id: int


class AnalyzeService:
    def __init__(
        self,
        *,
        cfg: YamlConfig,
        llm: LLMParser | None,
    ) -> None:
        self._cfg = cfg
        self._llm = llm

    async def analyze(
        self,
        conn: aiosqlite.Connection,
        *,
        user_id: int,
        window_days: int,
    ) -> AnalyzeResult:
        now_ts = int(time.time())
        day_s = 86_400
        # Always load 28d worth of history for rolling-best computation
        history = await repo.get_workouts_in_window(
            conn,
            user_id=user_id,
            since_ts=now_ts - self._cfg.windows.long_days * day_s,
            until_ts=now_ts,
        )

        result = engine.run(
            all_workouts_28d=history,
            window_days=window_days,
            cfg=self._cfg,
            now_ts=now_ts,
        )

        explanation: str | None = None
        if self._llm is not None:
            try:
                explanation = await self._llm.explain(
                    metrics=result["metrics"],
                    flags=result["flags"],
                    window_days=window_days,
                )
            except Exception as exc:
                log.warning("explain_failed", error=str(exc))

        snapshot_id = await repo.save_snapshot(
            conn,
            user_id=user_id,
            window_days=window_days,
            metrics=result["metrics"],
            flags=result["flags"],
            explanation=explanation,
        )

        return AnalyzeResult(
            window_days=window_days,
            metrics=result["metrics"],
            flags=result["flags"],
            explanation=explanation,
            snapshot_id=snapshot_id,
        )
