"""Analyze service: load window → run rules engine → LLM explain → save snapshot."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import aiosqlite

from pwrbot.config import YamlConfig
from pwrbot.db import repo
from pwrbot.llm.codex_client import CodexClient
from pwrbot.logging_setup import get_logger
from pwrbot.parsing.llm_parser import LLMParser
from pwrbot.rules import engine
from pwrbot.rules.recommendation import NextWorkoutRecommendation, recommend_next_workout

log = get_logger(__name__)


@dataclass(slots=True)
class ExplainBackendResult:
    text: str | None
    latency_s: float | None
    error: str | None


@dataclass(slots=True)
class AnalyzeResult:
    window_days: int
    metrics: dict[str, Any]
    flags: list[dict[str, Any]]
    explanation_gemma: ExplainBackendResult
    explanation_codex: ExplainBackendResult
    snapshot_id: int
    next_workout: NextWorkoutRecommendation | None = None


class AnalyzeService:
    def __init__(
        self,
        *,
        cfg: YamlConfig,
        llm: LLMParser | None,
        codex: CodexClient | None = None,
    ) -> None:
        self._cfg = cfg
        self._llm = llm
        self._codex = codex

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
        next_workout = recommend_next_workout(
            metrics=result["metrics"],
            flags=result["flags"],
            thresholds=self._cfg.thresholds,
        )

        gemma_result, codex_result = await asyncio.gather(
            self._call_gemma(
                metrics=result["metrics"],
                flags=result["flags"],
                window_days=window_days,
            ),
            self._call_codex(
                metrics=result["metrics"],
                flags=result["flags"],
                window_days=window_days,
            ),
            return_exceptions=True,
        )
        explanation_gemma = self._normalize_explain_result(
            gemma_result, backend="gemma"
        )
        explanation_codex = self._normalize_explain_result(
            codex_result, backend="codex"
        )

        snapshot_id = await repo.save_snapshot(
            conn,
            user_id=user_id,
            window_days=window_days,
            metrics=result["metrics"],
            flags=result["flags"],
            explanation=explanation_gemma.text,
        )

        return AnalyzeResult(
            window_days=window_days,
            metrics=result["metrics"],
            flags=result["flags"],
            explanation_gemma=explanation_gemma,
            explanation_codex=explanation_codex,
            snapshot_id=snapshot_id,
            next_workout=next_workout,
        )

    async def _call_gemma(
        self,
        *,
        metrics: dict[str, Any],
        flags: list[dict[str, Any]],
        window_days: int,
    ) -> ExplainBackendResult:
        if self._llm is None:
            return ExplainBackendResult(text=None, latency_s=None, error="disabled")

        started_at = time.monotonic()
        try:
            text = await self._llm.explain(
                metrics=metrics,
                flags=flags,
                window_days=window_days,
            )
        except Exception as exc:
            latency_s = time.monotonic() - started_at
            log.warning("explain_failed", backend="gemma", error=str(exc))
            return ExplainBackendResult(text=None, latency_s=latency_s, error=str(exc))
        latency_s = time.monotonic() - started_at
        return ExplainBackendResult(text=text, latency_s=latency_s, error=None)

    async def _call_codex(
        self,
        *,
        metrics: dict[str, Any],
        flags: list[dict[str, Any]],
        window_days: int,
    ) -> ExplainBackendResult:
        if self._codex is None:
            return ExplainBackendResult(text=None, latency_s=None, error="disabled")
        if self._llm is None:
            return ExplainBackendResult(
                text=None,
                latency_s=None,
                error="gemma_prompt_unavailable",
            )

        started_at = time.monotonic()
        try:
            system, user = self._llm.render_explain_prompt(
                metrics=metrics,
                flags=flags,
                window_days=window_days,
            )
            text = await self._codex.explain(
                system,
                user,
                timeout_s=self._cfg.llm.codex.timeout_s,
            )
        except Exception as exc:
            latency_s = time.monotonic() - started_at
            log.warning("explain_failed", backend="codex", error=str(exc))
            return ExplainBackendResult(text=None, latency_s=latency_s, error=str(exc))
        latency_s = time.monotonic() - started_at
        return ExplainBackendResult(text=text, latency_s=latency_s, error=None)

    def _normalize_explain_result(
        self,
        result: ExplainBackendResult | BaseException,
        *,
        backend: str,
    ) -> ExplainBackendResult:
        if isinstance(result, ExplainBackendResult):
            return result
        log.warning("explain_failed", backend=backend, error=str(result))
        return ExplainBackendResult(text=None, latency_s=None, error=str(result))
