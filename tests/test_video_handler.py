"""Tests for the video Telegram handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pwrbot.bot.handlers.video import handle_video
from pwrbot.services.technique import TechniqueResult, VideoTooLongError
from pwrbot.video.frame_extractor import FrameExtractionError


def _make_message(*, has_video: bool = True, caption: str | None = None) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 123
    msg.chat = MagicMock()
    msg.chat.id = 123
    msg.caption = caption
    msg.answer = AsyncMock()
    msg.bot = MagicMock()
    msg.bot.send_chat_action = AsyncMock()
    msg.bot.download = AsyncMock()

    if has_video:
        video = MagicMock()
        video.file_id = "file_abc123"
        msg.video = video
        msg.video_note = None
    else:
        msg.video = None
        msg.video_note = None

    return msg


@pytest.fixture
def technique_svc() -> MagicMock:
    svc = MagicMock()
    svc.analyze_video = AsyncMock(
        return_value=TechniqueResult(
            analysis_text="Техника хорошая.",
            frame_count=4,
            duration_s=5.0,
            model_used="gemma4:e4b",
            db_id=1,
        )
    )
    return svc


async def test_handle_video_happy_path(conn, technique_svc) -> None:
    from pwrbot.db import repo

    await repo.get_or_create_user(conn, telegram_id=123)
    msg = _make_message(caption="присед 140")

    with patch("pwrbot.bot.handlers.video.repo") as mock_repo:
        mock_repo.get_or_create_user = AsyncMock(return_value=1)
        await handle_video(msg, conn, technique_svc)

    # Should send acknowledgment, then analysis result
    assert msg.answer.call_count == 2
    first_call = msg.answer.call_args_list[0][0][0]
    assert "анализирую" in first_call.lower()
    second_call = msg.answer.call_args_list[1][0][0]
    assert "Техника хорошая." in second_call

    # Verify service was called with exercise_hint from caption
    technique_svc.analyze_video.assert_called_once()
    call_kwargs = technique_svc.analyze_video.call_args[1]
    assert call_kwargs["exercise_hint"] == "присед 140"


async def test_handle_video_no_caption(conn, technique_svc) -> None:
    msg = _make_message(caption=None)

    with patch("pwrbot.bot.handlers.video.repo") as mock_repo:
        mock_repo.get_or_create_user = AsyncMock(return_value=1)
        await handle_video(msg, conn, technique_svc)

    call_kwargs = technique_svc.analyze_video.call_args[1]
    assert call_kwargs["exercise_hint"] is None


async def test_handle_video_too_long(conn) -> None:
    svc = MagicMock()
    svc.analyze_video = AsyncMock(side_effect=VideoTooLongError("Видео слишком длинное"))
    msg = _make_message()

    with patch("pwrbot.bot.handlers.video.repo") as mock_repo:
        mock_repo.get_or_create_user = AsyncMock(return_value=1)
        await handle_video(msg, conn, svc)

    last_answer = msg.answer.call_args_list[-1][0][0]
    assert "слишком длинное" in last_answer.lower()


async def test_handle_video_extraction_error(conn) -> None:
    svc = MagicMock()
    svc.analyze_video = AsyncMock(
        side_effect=FrameExtractionError("Cannot open video")
    )
    msg = _make_message()

    with patch("pwrbot.bot.handlers.video.repo") as mock_repo:
        mock_repo.get_or_create_user = AsyncMock(return_value=1)
        await handle_video(msg, conn, svc)

    last_answer = msg.answer.call_args_list[-1][0][0]
    assert "не удалось обработать" in last_answer.lower()


async def test_handle_video_no_file(conn) -> None:
    svc = MagicMock()
    msg = _make_message(has_video=False)

    with patch("pwrbot.bot.handlers.video.repo") as mock_repo:
        mock_repo.get_or_create_user = AsyncMock(return_value=1)
        await handle_video(msg, conn, svc)

    last_answer = msg.answer.call_args_list[-1][0][0]
    assert "не удалось получить" in last_answer.lower()
