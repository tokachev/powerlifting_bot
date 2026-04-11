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

from dataclasses import dataclass

import aiosqlite
from pydantic import BaseModel

from pwrbot.config import YamlConfig
from pwrbot.db import repo
from pwrbot.domain.catalog import Catalog
from pwrbot.domain.models import WorkoutPayload
from pwrbot.logging_setup import get_logger
from pwrbot.parsing.normalize import to_repo_exercises
from pwrbot.parsing.pipeline import ParseError, ParsingPipeline, UnresolvedExercise
from pwrbot.services.analyze import AnalyzeResult, AnalyzeService

log = get_logger(__name__)


class PendingClarification(BaseModel):
    """Serializable pending parse: what the user sent, what we parsed, and which
    exercises still need resolution. Stored in aiogram FSM state between messages."""

    source_text: str
    performed_at: int
    payload: WorkoutPayload
    unresolved: list[UnresolvedExercise]


@dataclass(slots=True)
class IngestResult:
    workout_id: int
    payload: WorkoutPayload | None
    analysis: AnalyzeResult | None
    parse_error: str | None = None
    pending: PendingClarification | None = None


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
                workout_id=0, payload=None, analysis=None, parse_error=str(exc)
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
        return await self._persist_and_analyze(
            conn,
            user_id=user_id,
            source_text=pending.source_text,
            performed_at=pending.performed_at,
            payload=pending.payload,
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
        return IngestResult(workout_id=workout_id, payload=payload, analysis=analysis)
