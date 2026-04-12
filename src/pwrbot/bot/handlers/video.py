"""Handle video / video_note messages for technique analysis."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

import aiosqlite
from aiogram import F, Router
from aiogram.types import BufferedInputFile, Message

from pwrbot.db import repo
from pwrbot.logging_setup import get_logger
from pwrbot.services.technique import TechniqueAnalysisService, VideoTooLongError
from pwrbot.video.frame_extractor import FrameExtractionError

log = get_logger(__name__)

router = Router()


@router.message(F.video | F.video_note)
async def handle_video(
    message: Message,
    conn: aiosqlite.Connection,
    technique_svc: TechniqueAnalysisService,
) -> None:
    if message.from_user is None:
        return

    await message.answer("Получил видео, анализирую технику... Это может занять 30-60 секунд.")
    await message.bot.send_chat_action(message.chat.id, "typing")

    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)

    file_obj = message.video or message.video_note
    if file_obj is None:
        await message.answer("Не удалось получить видео.")
        return

    exercise_hint = (message.caption or "").strip() or None

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        await message.bot.download(file_obj.file_id, destination=tmp_path)

        result = await technique_svc.analyze_video(
            conn,
            user_id=uid,
            video_path=tmp_path,
            exercise_hint=exercise_hint,
            telegram_file_id=file_obj.file_id,
        )

        # Send problem frame screenshots first (if any)
        for i, frame_b64 in enumerate(result.problem_frames_b64, start=1):
            photo_bytes = base64.b64decode(frame_b64)
            photo = BufferedInputFile(photo_bytes, filename=f"frame_{i}.jpg")
            caption = f"Стоп-кадр {i}: ошибка техники" if len(result.problem_frames_b64) > 1 else "Стоп-кадр: ошибка техники"
            await message.answer_photo(photo, caption=caption)

        await message.answer(result.analysis_text)

    except VideoTooLongError as exc:
        await message.answer(str(exc))
    except FrameExtractionError:
        log.exception("frame_extraction_failed")
        await message.answer(
            "Не удалось обработать видео. Попробуй другой формат (MP4) "
            "или более короткий ролик."
        )
    except Exception:
        log.exception("video_analysis_failed")
        await message.answer("Ошибка при анализе видео. Попробуй позже.")
    finally:
        tmp_path.unlink(missing_ok=True)
