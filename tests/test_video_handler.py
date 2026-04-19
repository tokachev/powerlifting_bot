"""Tests for the video Telegram handler."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

from pwrbot.bot.handlers.video import handle_video
from pwrbot.services.technique import TechniqueResult, VideoTooLongError
from pwrbot.video.frame_extractor import FrameExtractionError

# Minimal valid JPEG (1x1 pixel) for photo tests
_TINY_JPEG_B64 = base64.b64encode(
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.\' ',#\x1c\x1c(7),01444\x1f\'9=82<.342"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\xdb\x9e\xa7\x93\xff\xd9"
).decode("ascii")


def _make_message(*, has_video: bool = True, caption: str | None = None) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 123
    msg.chat = MagicMock()
    msg.chat.id = 123
    msg.caption = caption
    msg.answer = AsyncMock()
    msg.answer_photo = AsyncMock()
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


def _make_technique_result(*, collage: str = "") -> TechniqueResult:
    return TechniqueResult(
        analysis_text="Техника хорошая.",
        frame_count=4,
        duration_s=5.0,
        model_used="gemma4:e4b",
        db_id=1,
        collage_b64=collage,
    )


async def test_handle_video_happy_path_no_problems(conn) -> None:
    svc = MagicMock()
    svc.analyze_video = AsyncMock(return_value=_make_technique_result())
    msg = _make_message(caption="присед 140")

    with patch("pwrbot.bot.handlers.video.repo") as mock_repo:
        mock_repo.get_or_create_user = AsyncMock(return_value=1)
        await handle_video(msg, conn, svc)

    # Acknowledgment + text reply, no photos
    assert msg.answer.call_count == 2
    assert msg.answer_photo.call_count == 0
    first_call = msg.answer.call_args_list[0][0][0]
    assert "анализирую" in first_call.lower()
    second_call = msg.answer.call_args_list[1][0][0]
    assert "Техника хорошая." in second_call

    svc.analyze_video.assert_called_once()
    call_kwargs = svc.analyze_video.call_args[1]
    assert call_kwargs["exercise_hint"] == "присед 140"


async def test_handle_video_with_collage(conn) -> None:
    svc = MagicMock()
    svc.analyze_video = AsyncMock(
        return_value=_make_technique_result(collage=_TINY_JPEG_B64)
    )
    msg = _make_message()

    with patch("pwrbot.bot.handlers.video.repo") as mock_repo:
        mock_repo.get_or_create_user = AsyncMock(return_value=1)
        await handle_video(msg, conn, svc)

    # 1 collage photo sent, then text
    assert msg.answer_photo.call_count == 1
    photo_call = msg.answer_photo.call_args
    assert "1-4" in photo_call[1]["caption"]
    assert msg.answer.call_count == 2  # ack + analysis text


async def test_handle_video_no_caption(conn) -> None:
    svc = MagicMock()
    svc.analyze_video = AsyncMock(return_value=_make_technique_result())
    msg = _make_message(caption=None)

    with patch("pwrbot.bot.handlers.video.repo") as mock_repo:
        mock_repo.get_or_create_user = AsyncMock(return_value=1)
        await handle_video(msg, conn, svc)

    call_kwargs = svc.analyze_video.call_args[1]
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
