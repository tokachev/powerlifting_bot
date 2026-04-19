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
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
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
CANCEL_TOKEN = "__cancel__"


def build_suggestion_keyboard(suggestions: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key in suggestions[:3]:
        b.button(text=key, callback_data=f"{CB_PREFIX}{key}")
    b.button(text="пропустить", callback_data=f"{CB_PREFIX}{SKIP_TOKEN}")
    b.button(text="❌ отменить черновик", callback_data=f"{CB_PREFIX}{CANCEL_TOKEN}")
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
    # Ack the callback query IMMEDIATELY — Telegram invalidates it after ~15s,
    # and finalize_pending below can take 60s+ due to LLM calls.
    await cb.answer()

    choice = (cb.data or "")[len(CB_PREFIX) :]

    # Explicit cancel — wipe state, acknowledge, done.
    if choice == CANCEL_TOKEN:
        await state.clear()
        try:
            await cb.message.edit_text("Черновик отменён.")
        except Exception:
            await cb.message.answer("Черновик отменён.")
        return

    data = await state.get_data()
    pending = PendingClarification.model_validate_json(data["pending"])
    cursor: int = data["cursor"]

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
        return

    # All resolved → persist + analyze. Show a progress stub first so the user
    # sees feedback while the LLM runs (can take 60-90s).
    if cb.from_user is None:
        return
    try:
        await cb.message.edit_text("Сохраняю и анализирую тренировку…")
    except Exception:
        pass
    uid = await repo.get_or_create_user(conn, telegram_id=cb.from_user.id)
    result = await ingest.finalize_pending(conn, user_id=uid, pending=pending)
    await state.clear()
    if result.parse_error:
        try:
            await cb.message.edit_text(result.parse_error)
        except Exception:
            await cb.message.answer(result.parse_error)
        return
    prefix = "Дописал к последней тренировке.\n\n" if result.was_append else ""
    reply = prefix + format_ingest_reply(
        result.payload, result.analysis, result.rm_estimates,
        result.body_weight_kg, result.new_prs,
    )
    try:
        await cb.message.edit_text(reply)
    except Exception:
        await cb.message.answer(reply)


# If the user sends a new workout text mid-dialog, treat it as an explicit
# replacement: drop the pending draft and re-parse the new message from scratch.
# Slash-commands (/log, /add, /cancel…) fall through to their own routers via
# the ~F.text.startswith("/") filter.
@router.message(ClarifyStates.resolving, F.text & ~F.text.startswith("/"))
async def reparse_text_in_clarify(
    message: Message,
    state: FSMContext,
    conn: aiosqlite.Connection,
    ingest: IngestService,
) -> None:
    data = await state.get_data()
    pending_raw = data.get("pending")
    n_unresolved = 0
    if pending_raw:
        try:
            n_unresolved = len(
                PendingClarification.model_validate_json(pending_raw).unresolved
            )
        except Exception:
            n_unresolved = 0
    log.info("clarify_draft_dropped", unresolved_remaining=n_unresolved)
    await state.clear()
    await message.answer("Сбросил предыдущий черновик, парсю новое сообщение.")
    # Lazy import to avoid a circular import (log → clarify → log).
    from pwrbot.bot.handlers.log import ingest_text
    await ingest_text(message, message.text or "", conn, ingest, state)


def unwrap_exercise(ex: ExercisePayload) -> ExercisePayload:
    # Small helper re-exported for tests; keeps pipeline/ingest decoupled.
    return ex
