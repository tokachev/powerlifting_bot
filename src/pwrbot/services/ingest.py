"""Ingest service: parse → persist → auto-analyze.

After a successful /log the bot runs the 7-day rules engine and asks the LLM
to explain the findings. Both the parsed workout summary and the mini-analysis
text are returned to the handler layer for display.

If the parser returns exercises that couldn't be canonicalized, the service
does NOT persist. Instead it wraps everything into a PendingClarification and
returns it so the handler can ask the user. Once the user answers, the handler
calls `finalize_pending()` to actually persist and run the analysis.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import aiosqlite
from pydantic import BaseModel

from pwrbot.config import YamlConfig
from pwrbot.db import repo
from pwrbot.domain.catalog import Catalog
from pwrbot.domain.models import WorkoutPayload
from pwrbot.logging_setup import get_logger
from pwrbot.metrics.pr import DetectedPR, detect_e1rm_prs
from pwrbot.parsing.normalize import to_repo_exercises
from pwrbot.parsing.pipeline import ParseError, ParsingPipeline, UnresolvedExercise
from pwrbot.rules.one_rm import OneRMEstimate, compute_1rm_estimates
from pwrbot.services.analyze import AnalyzeResult, AnalyzeService

log = get_logger(__name__)


class PendingClarification(BaseModel):
    """Serializable pending parse: what the user sent, what we parsed, and which
    exercises still need resolution. Stored in aiogram FSM state between messages.

    ``target_workout_id`` is set when the user invoked /add — finalize_pending
    will then append the resolved payload to that workout instead of creating
    a new one.
    """

    source_text: str
    performed_at: int
    payload: WorkoutPayload
    unresolved: list[UnresolvedExercise]
    target_workout_id: int | None = None


@dataclass(slots=True)
class IngestResult:
    workout_id: int
    payload: WorkoutPayload | None
    analysis: AnalyzeResult | None
    rm_estimates: list[OneRMEstimate] = field(default_factory=list)
    new_prs: list[DetectedPR] = field(default_factory=list)
    body_weight_kg: float | None = None
    parse_error: str | None = None
    pending: PendingClarification | None = None
    was_append: bool = False


class IngestService:
    def __init__(
        self,
        *,
        pipeline: ParsingPipeline,
        analyzer: AnalyzeService,
        catalog: Catalog,
        cfg: YamlConfig,
    ) -> None:
        self._pipeline = pipeline
        self._analyzer = analyzer
        self._catalog = catalog
        self._cfg = cfg

    async def ingest(
        self,
        conn: aiosqlite.Connection,
        *,
        user_id: int,
        source_text: str,
    ) -> IngestResult:
        try:
            result = await self._pipeline.parse(source_text)
        except ParseError as exc:
            log.warning("ingest_parse_error", error=str(exc))
            return IngestResult(
                workout_id=0, payload=None, analysis=None,
                parse_error=exc.user_message or "Не смог распарсить тренировку.",
            )

        payload = result.payload
        performed_at = int(payload.performed_at.timestamp()) if payload.performed_at else 0

        if result.unresolved:
            log.info("ingest_pending_clarification", unresolved=len(result.unresolved))
            return IngestResult(
                workout_id=0,
                payload=payload,
                analysis=None,
                pending=PendingClarification(
                    source_text=source_text,
                    performed_at=performed_at,
                    payload=payload,
                    unresolved=result.unresolved,
                ),
            )

        return await self._persist_and_analyze(
            conn,
            user_id=user_id,
            source_text=source_text,
            performed_at=performed_at,
            payload=payload,
        )

    async def finalize_pending(
        self,
        conn: aiosqlite.Connection,
        *,
        user_id: int,
        pending: PendingClarification,
    ) -> IngestResult:
        """Called after the user has answered all clarification questions.
        Assumes `pending.payload.exercises` has been patched with user choices
        (canonical_name set where the user picked one; still None where the
        user chose to skip)."""
        if pending.target_workout_id is not None:
            exists = await repo.workout_exists(
                conn, workout_id=pending.target_workout_id, user_id=user_id,
            )
            if not exists:
                return IngestResult(
                    workout_id=0,
                    payload=pending.payload,
                    analysis=None,
                    parse_error="Тренировка для дополнения уже удалена.",
                )
            return await self._append_and_analyze(
                conn,
                user_id=user_id,
                workout_id=pending.target_workout_id,
                performed_at=pending.performed_at,
                addition_text=pending.source_text,
                payload=pending.payload,
            )
        return await self._persist_and_analyze(
            conn,
            user_id=user_id,
            source_text=pending.source_text,
            performed_at=pending.performed_at,
            payload=pending.payload,
        )

    async def append_to_last(
        self,
        conn: aiosqlite.Connection,
        *,
        user_id: int,
        source_text: str,
    ) -> IngestResult:
        """Parse `source_text` and append the resulting exercises to the user's
        most recent workout. Same parse/clarify pipeline as ``ingest``; the only
        difference is persistence — no new workout row is created."""
        last = await repo.get_last_workout(conn, user_id=user_id)
        if last is None:
            return IngestResult(
                workout_id=0,
                payload=None,
                analysis=None,
                parse_error="Нет тренировок для дополнения.",
            )

        try:
            result = await self._pipeline.parse(source_text)
        except ParseError as exc:
            log.warning("append_parse_error", error=str(exc))
            return IngestResult(
                workout_id=0, payload=None, analysis=None,
                parse_error=exc.user_message or "Не смог распарсить тренировку.",
            )

        payload = result.payload

        if result.unresolved:
            log.info(
                "append_pending_clarification",
                workout_id=last.id,
                unresolved=len(result.unresolved),
            )
            return IngestResult(
                workout_id=0,
                payload=payload,
                analysis=None,
                pending=PendingClarification(
                    source_text=source_text,
                    performed_at=last.performed_at,
                    payload=payload,
                    unresolved=result.unresolved,
                    target_workout_id=last.id,
                ),
            )

        return await self._append_and_analyze(
            conn,
            user_id=user_id,
            workout_id=last.id,
            performed_at=last.performed_at,
            addition_text=source_text,
            payload=payload,
        )

    async def _persist_and_analyze(
        self,
        conn: aiosqlite.Connection,
        *,
        user_id: int,
        source_text: str,
        performed_at: int,
        payload: WorkoutPayload,
    ) -> IngestResult:
        exercises = to_repo_exercises(payload, self._catalog)
        workout_id = await repo.insert_workout(
            conn,
            user_id=user_id,
            performed_at=performed_at,
            source_text=source_text,
            exercises=exercises,
            notes=payload.notes,
        )
        log.info("ingest_ok", workout_id=workout_id, exercises=len(exercises))

        analysis = await self._analyzer.analyze(
            conn,
            user_id=user_id,
            window_days=self._cfg.windows.short_days,
        )

        rm_estimates = await self._compute_rm(conn, user_id=user_id, payload=payload)

        new_prs = await self._detect_prs(
            conn, user_id=user_id, workout_id=workout_id,
            performed_at=performed_at, exercises=exercises,
        )

        bw_kg: float | None = None
        latest_bw = await repo.get_latest_body_weight(conn, user_id)
        if latest_bw is not None:
            bw_kg = latest_bw[0] / 1000.0

        return IngestResult(
            workout_id=workout_id,
            payload=payload,
            analysis=analysis,
            rm_estimates=rm_estimates,
            new_prs=new_prs,
            body_weight_kg=bw_kg,
        )

    async def _append_and_analyze(
        self,
        conn: aiosqlite.Connection,
        *,
        user_id: int,
        workout_id: int,
        performed_at: int,
        addition_text: str,
        payload: WorkoutPayload,
    ) -> IngestResult:
        new_exercises = to_repo_exercises(payload, self._catalog)
        await repo.append_to_workout(
            conn,
            workout_id=workout_id,
            exercises=new_exercises,
            addition_text=addition_text,
        )
        log.info(
            "append_ok", workout_id=workout_id, exercises=len(new_exercises),
        )

        analysis = await self._analyzer.analyze(
            conn, user_id=user_id, window_days=self._cfg.windows.short_days,
        )

        rm_estimates = await self._compute_rm(conn, user_id=user_id, payload=payload)

        new_prs = await self._detect_prs(
            conn, user_id=user_id, workout_id=workout_id,
            performed_at=performed_at, exercises=new_exercises,
        )

        bw_kg: float | None = None
        latest_bw = await repo.get_latest_body_weight(conn, user_id)
        if latest_bw is not None:
            bw_kg = latest_bw[0] / 1000.0

        return IngestResult(
            workout_id=workout_id,
            payload=payload,
            analysis=analysis,
            rm_estimates=rm_estimates,
            new_prs=new_prs,
            body_weight_kg=bw_kg,
            was_append=True,
        )

    async def _compute_rm(
        self,
        conn: aiosqlite.Connection,
        *,
        user_id: int,
        payload: WorkoutPayload,
    ) -> list[OneRMEstimate]:
        """Compute 1RM estimates for big-3 exercises in the workout."""
        target_exercises: list[tuple[str, str | None]] = []
        for ex in payload.exercises:
            if ex.canonical_name is None:
                continue
            entry = self._catalog.by_canonical(ex.canonical_name)
            if entry is not None and entry.target_group is not None:
                target_exercises.append((entry.canonical_name, entry.target_group))

        if not target_exercises:
            return []

        now_ts = int(time.time())
        day_s = 86_400
        history = await repo.get_workouts_in_window(
            conn,
            user_id=user_id,
            since_ts=now_ts - self._cfg.windows.rm_window_days * day_s,
            until_ts=now_ts,
        )
        return compute_1rm_estimates(history, target_exercises)

    async def _detect_prs(
        self,
        conn: aiosqlite.Connection,
        *,
        user_id: int,
        workout_id: int,
        performed_at: int,
        exercises: list[repo.ExerciseRow],
    ) -> list[DetectedPR]:
        """Detect e1RM personal records for exercises in this workout."""
        canonical_names = {
            ex.canonical_name
            for ex in exercises
            if ex.canonical_name is not None
        }
        if not canonical_names:
            return []

        previous_bests: dict[str, float] = {}
        for name in canonical_names:
            best_g = await repo.get_best_e1rm_for_exercise(
                conn, user_id=user_id, canonical_name=name,
            )
            if best_g is not None:
                previous_bests[name] = best_g / 1000.0

        detected = detect_e1rm_prs(exercises, previous_bests)
        for pr in detected:
            await repo.insert_personal_record(
                conn,
                user_id=user_id,
                canonical_name=pr.canonical_name,
                pr_type=pr.pr_type,
                weight_g=round(pr.weight_kg * 1000),
                reps=pr.reps,
                estimated_1rm_g=round(pr.estimated_1rm_kg * 1000),
                previous_value_g=(
                    round(pr.previous_1rm_kg * 1000)
                    if pr.previous_1rm_kg is not None
                    else None
                ),
                workout_id=workout_id,
                achieved_at=performed_at,
            )
        if detected:
            log.info("prs_detected", count=len(detected))
        return detected
