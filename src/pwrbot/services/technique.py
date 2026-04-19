"""Video technique analysis: extract frames, send to vision LLM, persist result."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import aiosqlite
from pydantic import BaseModel, Field

from pwrbot.db import repo
from pwrbot.llm.ollama_client import OllamaClient
from pwrbot.llm.prompt_loader import PromptLoader
from pwrbot.logging_setup import get_logger
from pwrbot.video.frame_extractor import ExtractedFrames, extract_key_frames
from pwrbot.video.pose_annotator import build_collage

log = get_logger(__name__)


class TechniqueAnalysisResponse(BaseModel):
    """LLM structured output: analysis text + indices of problematic frames."""

    analysis_text: str
    problem_frame_indices: list[int] = Field(default_factory=list)


@dataclass(slots=True)
class TechniqueResult:
    analysis_text: str
    frame_count: int
    duration_s: float
    model_used: str
    db_id: int
    collage_b64: str = ""


class TechniqueAnalysisService:
    def __init__(
        self,
        *,
        ollama: OllamaClient,
        prompts: PromptLoader,
        vision_model: str | None = None,
        vision_timeout_s: int = 120,
        max_frames: int = 6,
        resize_width: int = 720,
        max_video_duration_s: int = 60,
    ) -> None:
        self._ollama = ollama
        self._prompts = prompts
        self._vision_model = vision_model
        self._vision_timeout_s = vision_timeout_s
        self._max_frames = max_frames
        self._resize_width = resize_width
        self._max_video_duration_s = max_video_duration_s

    async def analyze_video(
        self,
        conn: aiosqlite.Connection,
        *,
        user_id: int,
        video_path: Path,
        exercise_hint: str | None = None,
        telegram_file_id: str | None = None,
    ) -> TechniqueResult:
        extracted = await asyncio.to_thread(
            extract_key_frames,
            video_path,
            max_frames=self._max_frames,
            resize_width=self._resize_width,
        )

        if extracted.duration_s > self._max_video_duration_s:
            raise VideoTooLongError(
                f"Видео слишком длинное ({extracted.duration_s:.0f}с), "
                f"максимум {self._max_video_duration_s}с."
            )

        llm_resp = await self._call_vision(extracted, exercise_hint)
        model_used = self._vision_model or self._ollama._model

        # Build collage: all frames numbered, problem frames get pose annotation
        collage_b64 = await asyncio.to_thread(
            build_collage,
            extracted.frames_b64,
            llm_resp.problem_frame_indices,
        )

        db_id = await repo.insert_video_analysis(
            conn,
            user_id=user_id,
            exercise_hint=exercise_hint,
            frame_count=len(extracted.frames_b64),
            duration_s=extracted.duration_s,
            analysis_text=llm_resp.analysis_text,
            model_used=model_used,
            telegram_file_id=telegram_file_id,
        )

        log.info(
            "technique_analysis_done",
            db_id=db_id,
            frames=len(extracted.frames_b64),
            problem_indices=llm_resp.problem_frame_indices,
            duration_s=extracted.duration_s,
            motion_window=extracted.motion_window,
        )

        return TechniqueResult(
            analysis_text=llm_resp.analysis_text,
            frame_count=len(extracted.frames_b64),
            duration_s=extracted.duration_s,
            model_used=model_used,
            db_id=db_id,
            collage_b64=collage_b64,
        )

    async def _call_vision(
        self, extracted: ExtractedFrames, exercise_hint: str | None
    ) -> TechniqueAnalysisResponse:
        if exercise_hint:
            exercise_context = f"Упражнение: {exercise_hint}."
        else:
            exercise_context = "Упражнение не указано — определи по кадрам."

        tmpl = self._prompts.render(
            "technique_analysis",
            frame_count=str(len(extracted.frames_b64)),
            exercise_context=exercise_context,
        )
        system, _, user = tmpl.partition("USER:")
        system = system.replace("SYSTEM:", "").strip()
        user = user.strip() or tmpl

        return await self._ollama.chat_vision_json(
            system=system,
            user=user,
            images=extracted.frames_b64,
            schema_model=TechniqueAnalysisResponse,
            model_override=self._vision_model,
        )


class VideoTooLongError(Exception):
    """Raised when the uploaded video exceeds the max duration."""
