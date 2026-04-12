"""Tests for TechniqueAnalysisService (mocked Ollama + frame extractor)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from pwrbot.llm.ollama_client import OllamaClient
from pwrbot.llm.prompt_loader import PromptLoader
from pwrbot.services.technique import (
    TechniqueAnalysisService,
    TechniqueResult,
    VideoTooLongError,
)
from pwrbot.video.frame_extractor import ExtractedFrames

REPO_ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_RESPONSE = "Техника хорошая. Глубина достаточная, спина нейтральная."


def _fake_extracted(duration_s: float = 5.0) -> ExtractedFrames:
    return ExtractedFrames(
        frames_b64=["AAAA", "BBBB", "CCCC"],
        fps=30.0,
        total_frames=150,
        duration_s=duration_s,
    )


def _vision_reply(content: str) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": content}}


def _make_service(http_client: httpx.AsyncClient) -> TechniqueAnalysisService:
    client = OllamaClient(
        base_url="http://fake", model="gemma4:e4b", client=http_client
    )
    prompts = PromptLoader(REPO_ROOT / "prompts")
    return TechniqueAnalysisService(ollama=client, prompts=prompts)


async def test_analyze_video_happy_path(conn) -> None:
    from pwrbot.db import repo

    uid = await repo.get_or_create_user(conn, telegram_id=111)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert "images" in body["messages"][1]
        assert len(body["messages"][1]["images"]) == 3
        return httpx.Response(200, json=_vision_reply(ANALYSIS_RESPONSE))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        svc = _make_service(http)

        with patch(
            "pwrbot.services.technique.extract_key_frames",
            return_value=_fake_extracted(),
        ):
            result = await svc.analyze_video(
                conn,
                user_id=uid,
                video_path=Path("/fake/video.mp4"),
                exercise_hint="присед",
                telegram_file_id="AgACAgIAA",
            )

    assert isinstance(result, TechniqueResult)
    assert result.analysis_text == ANALYSIS_RESPONSE
    assert result.frame_count == 3
    assert result.duration_s == 5.0
    assert result.model_used == "gemma4:e4b"
    assert result.db_id > 0

    # Check DB row was created
    rows = await repo.get_video_analyses(conn, user_id=uid)
    assert len(rows) == 1
    assert rows[0].exercise_hint == "присед"
    assert rows[0].analysis_text == ANALYSIS_RESPONSE


async def test_analyze_video_no_hint(conn) -> None:
    from pwrbot.db import repo

    uid = await repo.get_or_create_user(conn, telegram_id=222)

    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        captured.append(body)
        return httpx.Response(200, json=_vision_reply(ANALYSIS_RESPONSE))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        svc = _make_service(http)

        with patch(
            "pwrbot.services.technique.extract_key_frames",
            return_value=_fake_extracted(),
        ):
            result = await svc.analyze_video(
                conn,
                user_id=uid,
                video_path=Path("/fake/video.mp4"),
            )

    assert result.analysis_text == ANALYSIS_RESPONSE
    # The prompt should contain the "not specified" context
    user_msg = captured[0]["messages"][1]["content"]
    assert "не указано" in user_msg.lower()


async def test_video_too_long_raises(conn) -> None:
    from pwrbot.db import repo

    uid = await repo.get_or_create_user(conn, telegram_id=333)

    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, json=_vision_reply("ok"))
    )
    async with httpx.AsyncClient(transport=transport) as http:
        svc = _make_service(http)
        svc._max_video_duration_s = 10

        with (
            patch(
                "pwrbot.services.technique.extract_key_frames",
                return_value=_fake_extracted(duration_s=120.0),
            ),
            pytest.raises(VideoTooLongError),
        ):
            await svc.analyze_video(
                conn,
                user_id=uid,
                video_path=Path("/fake/long.mp4"),
            )


async def test_vision_model_override(conn) -> None:
    from pwrbot.db import repo

    uid = await repo.get_or_create_user(conn, telegram_id=444)

    captured_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        captured_models.append(body["model"])
        return httpx.Response(200, json=_vision_reply("ok"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OllamaClient(
            base_url="http://fake", model="gemma4:e4b", client=http
        )
        prompts = PromptLoader(REPO_ROOT / "prompts")
        svc = TechniqueAnalysisService(
            ollama=client, prompts=prompts, vision_model="llava:13b"
        )

        with patch(
            "pwrbot.services.technique.extract_key_frames",
            return_value=_fake_extracted(),
        ):
            result = await svc.analyze_video(
                conn,
                user_id=uid,
                video_path=Path("/fake/video.mp4"),
            )

    assert captured_models[0] == "llava:13b"
    assert result.model_used == "llava:13b"
