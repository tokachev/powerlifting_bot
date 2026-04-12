"""FSM-driven clarification flow for exercises the parser couldn't canonicalize.

Flow:
1. /log (or plain-text) parses a message → some exercises have no canonical_name
2. log.py stashes the PendingClarification in FSM state and asks the first question
   via an inline keyboard (3 suggestions + "пропустить").
3. Each button press lands here, updates the payload, and either asks the next
   question or calls IngestService.finalize_pending() to persist + analyze.
"""

from __future__ import annotations

import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from pwrbot.bot.formatting import format_ingest_reply
from pwrbot.db import repo
from pwrbot.domain.models import ExercisePayload
from pwrbot.logging_setup import get_logger
from pwrbot.services.ingest import IngestService, PendingClarification

router = Router()
log = get_logger(__name__)


class ClarifyStates(StatesGroup):
    resolving = State()


CB_PREFIX = "cl:"
SKIP_TOKEN = "__skip__"


def build_suggestion_keyboard(suggestions: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key in suggestions[:3]:
        b.button(text=key, callback_data=f"{CB_PREFIX}{key}")
    b.button(text="пропустить", callback_data=f"{CB_PREFIX}{SKIP_TOKEN}")
    b.adjust(1)
    return b.as_markup()


def format_clarify_question(raw_name: str, has_suggestions: bool) -> str:
    if has_suggestions:
        return (
            f"Не знаю упражнение «{raw_name}». Выбери ближайшее из каталога "
            f"или нажми «пропустить» — тогда это упражнение не войдёт в "
            f"метрики по паттернам."
        )
    return (
        f"Не знаю упражнение «{raw_name}» и не могу предложить ничего похожего "
        f"из каталога. Нажми «пропустить» — оно сохранится, но не попадёт в "
        f"pattern-метрики."
    )


async def start_clarification(
    message,
    state: FSMContext,
    pending: PendingClarification,
) -> None:
    """Called from log.py when ingest returns a pending result. Stores the
    pending parse in FSM state and sends the first question."""
    await state.set_state(ClarifyStates.resolving)
    await state.update_data(pending=pending.model_dump_json(), cursor=0)
    first = pending.unresolved[0]
    await message.answer(
        format_clarify_question(first.raw_name, bool(first.suggestions)),
        reply_markup=build_suggestion_keyboard(first.suggestions),
    )


@router.callback_query(ClarifyStates.resolving, F.data.startswith(CB_PREFIX))
async def on_pick(
    cb: CallbackQuery,
    state: FSMContext,
    conn: aiosqlite.Connection,
    ingest: IngestService,
) -> None:
    data = await state.get_data()
    pending = PendingClarification.model_validate_json(data["pending"])
    cursor: int = data["cursor"]

    choice = (cb.data or "")[len(CB_PREFIX) :]
    unres = pending.unresolved[cursor]

    # Apply the choice
    if choice != SKIP_TOKEN:
        idx = unres.index
        exercises = list(pending.payload.exercises)
        exercises[idx] = exercises[idx].model_copy(update={"canonical_name": choice})
        pending = pending.model_copy(
            update={"payload": pending.payload.model_copy(update={"exercises": exercises})}
        )

    cursor += 1

    if cursor < len(pending.unresolved):
        await state.update_data(pending=pending.model_dump_json(), cursor=cursor)
        nxt = pending.unresolved[cursor]
        try:
            await cb.message.edit_text(
                format_clarify_question(nxt.raw_name, bool(nxt.suggestions)),
                reply_markup=build_suggestion_keyboard(nxt.suggestions),
            )
        except Exception:
            await cb.message.answer(
                format_clarify_question(nxt.raw_name, bool(nxt.suggestions)),
                reply_markup=build_suggestion_keyboard(nxt.suggestions),
            )
        await cb.answer()
        return

    # All resolved → persist + analyze
    if cb.from_user is None:
        await cb.answer("нет пользователя")
        return
    uid = await repo.get_or_create_user(conn, telegram_id=cb.from_user.id)
    result = await ingest.finalize_pending(conn, user_id=uid, pending=pending)
    await state.clear()
    reply = format_ingest_reply(result.payload, result.analysis, result.rm_estimates)
    try:
        await cb.message.edit_text(reply)
    except Exception:
        await cb.message.answer(reply)
    await cb.answer("готово")


# Guard: ignore plain text while in clarify state so a typo doesn't get parsed
# as a new workout mid-dialog.
@router.message(ClarifyStates.resolving)
async def reject_text_in_clarify(message) -> None:
    await message.answer(
        "Ещё не ответил про предыдущее упражнение — нажми одну из кнопок выше "
        "или «пропустить»."
    )


def unwrap_exercise(ex: ExercisePayload) -> ExercisePayload:
    # Small helper re-exported for tests; keeps pipeline/ingest decoupled.
    return ex
