"""Orchestration: regex → LLM fallback → normalize → validate.

Returns a ParseResult: the normalized WorkoutPayload plus a list of exercises
that could not be canonicalized and need user clarification.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from pwrbot.config import YamlConfig
from pwrbot.domain.catalog import Catalog
from pwrbot.domain.models import ExercisePayload, SetPayload, WorkoutPayload
from pwrbot.logging_setup import get_logger
from pwrbot.parsing import normalize, preprocess, regex_parser
from pwrbot.parsing.llm_parser import LLMParser

log = get_logger(__name__)


class ParseError(Exception):
    """Couldn't parse the message after both regex and LLM attempts."""


class UnresolvedExercise(BaseModel):
    """An exercise whose canonical name couldn't be determined automatically."""

    index: int                                       # position in payload.exercises
    raw_name: str
    suggestions: list[str] = Field(default_factory=list)  # up to 3 catalog keys


class ParseResult(BaseModel):
    payload: WorkoutPayload
    unresolved: list[UnresolvedExercise] = Field(default_factory=list)


def _regex_to_payload(
    parsed: list[regex_parser.ParsedExercise],
) -> WorkoutPayload:
    """Build a WorkoutPayload from regex output. `performed_at` is left unset
    (None) — the pipeline fills it from the tail-metadata override, or falls
    back to `datetime.now(UTC)` as a single source of truth at the end of
    `ParsingPipeline.parse()`.
    """
    exercises = [
        ExercisePayload(
            raw_name=p.raw_name,
            sets=[
                SetPayload(
                    reps=s.reps,
                    weight_kg=s.weight_kg,
                    rpe=s.rpe,
                    is_warmup=s.is_warmup,
                )
                for s in p.sets
            ],
        )
        for p in parsed
    ]
    return WorkoutPayload(
        performed_at=None,
        exercises=exercises,
    )


class ParsingPipeline:
    def __init__(
        self,
        catalog: Catalog,
        cfg: YamlConfig,
        llm_parser: LLMParser | None = None,
    ) -> None:
        self._catalog = catalog
        self._cfg = cfg
        self._llm = llm_parser

    async def parse(self, text: str) -> ParseResult:
        """Parse user text into a normalized ParseResult. Raises ParseError on failure.

        Exercises that can't be canonicalized are returned in `unresolved` with
        up to 3 LLM-suggested catalog keys. The caller (ingest service) decides
        whether to persist immediately or ask the user first.
        """
        now = datetime.now(UTC)

        # 0) strip a header-date line so regex+LLM see only the workout body
        body, date_override = preprocess.extract_header_date(text, now)

        # 1) regex first
        parsed = regex_parser.parse(body)
        if parsed is not None:
            log.info("regex_parse_ok", exercises=len(parsed))
            payload = _regex_to_payload(parsed)
        else:
            if self._llm is None:
                raise ParseError("regex parser failed and no LLM parser configured")
            log.info("regex_parse_miss_llm_fallback")
            try:
                payload = await self._llm.parse_text(body)
            except Exception as exc:  # LLMParseError or network
                raise ParseError(f"LLM parse failed: {exc}") from exc

        # 2) catalog resolution + warmup rule
        payload = normalize.normalize_workout(payload, self._catalog, self._cfg)

        # 3) LLM canonicalization for still-unresolved names; collect unknowns
        unresolved: list[UnresolvedExercise] = []
        if self._llm is not None:
            new_exercises = []
            changed = False
            for idx, ex in enumerate(payload.exercises):
                if ex.canonical_name is not None:
                    new_exercises.append(ex)
                    continue
                try:
                    canon = await self._llm.canonicalize(ex.raw_name)
                except Exception as exc:
                    log.warning("canonicalize_failed", raw_name=ex.raw_name, error=str(exc))
                    unresolved.append(
                        UnresolvedExercise(index=idx, raw_name=ex.raw_name, suggestions=[])
                    )
                    new_exercises.append(ex)
                    continue
                if canon.canonical_name:
                    ex = ex.model_copy(update={"canonical_name": canon.canonical_name})
                    changed = True
                else:
                    unresolved.append(
                        UnresolvedExercise(
                            index=idx,
                            raw_name=ex.raw_name,
                            suggestions=list(canon.suggestions),
                        )
                    )
                new_exercises.append(ex)
            if changed:
                payload = payload.model_copy(update={"exercises": new_exercises})
        else:
            # No LLM → collect any catalog miss as unresolved (with no suggestions)
            for idx, ex in enumerate(payload.exercises):
                if ex.canonical_name is None:
                    unresolved.append(
                        UnresolvedExercise(index=idx, raw_name=ex.raw_name, suggestions=[])
                    )

        # make sure performed_at is set — priority: explicit override > LLM > now()
        if date_override is not None:
            payload = payload.model_copy(update={"performed_at": date_override})
        elif payload.performed_at is None:
            payload = payload.model_copy(update={"performed_at": now})

        return ParseResult(payload=payload, unresolved=unresolved)
