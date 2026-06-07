"""Analyze service: load window → run rules engine → LLM explain → save snapshot."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from pwrbot.config import YamlConfig
from pwrbot.db import repo
from pwrbot.llm.codex_client import CodexClient
from pwrbot.logging_setup import get_logger
from pwrbot.parsing.llm_parser import LLMParser
from pwrbot.rules import engine, volume
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


def _fmt_weight(kg: float) -> str:
    if kg == int(kg):
        return str(int(kg))
    return f"{kg:.1f}"


def _fmt_set_for_context(s: repo.SetRow) -> str:
    kg = s.weight_g / 1000.0
    weight = f"{_fmt_weight(kg)}кг" if kg else "собственный вес"
    rpe = f" @{_fmt_weight(s.rpe)}" if s.rpe is not None else ""
    return f"{s.reps}×{weight}{rpe}"


def _is_context_hard_set(
    s: repo.SetRow, *, rolling_best_kg: float | None, cfg: YamlConfig
) -> bool:
    if s.is_warmup:
        return False
    return volume.is_hard_set(
        reps=s.reps,
        weight_kg=s.weight_g / 1000.0,
        rpe=s.rpe,
        thresholds=cfg.thresholds,
        rolling_best_kg=rolling_best_kg,
    )


def _summarize_exercise_for_context(
    ex: repo.ExerciseRow, *, history: list[repo.WorkoutRow], cfg: YamlConfig
) -> dict[str, Any]:
    working_sets = [s for s in ex.sets if not s.is_warmup]
    rolling_best_kg = volume.rolling_best_weight_kg(history, ex.canonical_name)
    hard_sets = [
        s
        for s in working_sets
        if _is_context_hard_set(s, rolling_best_kg=rolling_best_kg, cfg=cfg)
    ]
    top_set = max(
        working_sets,
        key=lambda s: (s.weight_g, s.reps, s.rpe or 0.0),
        default=None,
    )
    return {
        "name": ex.canonical_name or ex.raw_name,
        "movement_pattern": ex.movement_pattern,
        "working_sets": len(working_sets),
        "hard_sets": len(hard_sets),
        "top_set": _fmt_set_for_context(top_set) if top_set is not None else None,
    }


def _build_training_context(
    *, history: list[repo.WorkoutRow], window_days: int, now_ts: int, cfg: YamlConfig
) -> dict[str, Any]:
    since_ts = now_ts - window_days * 86_400
    recent = [w for w in history if w.performed_at >= since_ts]
    recent = sorted(recent, key=lambda w: (w.performed_at, w.id))[-8:]
    return {
        "recent_workouts_count": len(recent),
        "recent_workouts": [
            {
                "date": datetime.fromtimestamp(w.performed_at, tz=UTC).date().isoformat(),
                "workout_id": w.id,
                "exercises": [
                    _summarize_exercise_for_context(ex, history=history, cfg=cfg)
                    for ex in w.exercises
                ],
            }
            for w in recent
        ],
    }


class AnalyzeService:

    def __init__(
        self,
        *,
        cfg: YamlConfig,
        llm: LLMParser | None,
        codex: CodexClient | None = None,
        gemma_enabled: bool = True,
    ) -> None:
        self._cfg = cfg
        self._llm = llm
        self._codex = codex
        self._gemma_enabled = gemma_enabled

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
        metrics = dict(result["metrics"])
        metrics["training_context"] = _build_training_context(
            history=history,
            window_days=window_days,
            now_ts=now_ts,
            cfg=self._cfg,
        )

        gemma_result, codex_result = await asyncio.gather(
            self._call_gemma(
                metrics=metrics,
                flags=result["flags"],
                window_days=window_days,
            ),
            self._call_codex(
                metrics=metrics,
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
            metrics=metrics,
            flags=result["flags"],
            explanation=explanation_gemma.text or explanation_codex.text,
        )

        return AnalyzeResult(
            window_days=window_days,
            metrics=metrics,
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
        if not self._gemma_enabled:
            return ExplainBackendResult(text=None, latency_s=None, error="disabled")
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
