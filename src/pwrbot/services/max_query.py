"""Service for answering free-form questions about rep maxes.

Resolves exercise names via the catalog, queries 90-day history, and computes
estimated 1RM / nRM using deterministic formulas from ``rules.one_rm``.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import aiosqlite

from pwrbot.config import YamlConfig
from pwrbot.db import repo
from pwrbot.domain.catalog import Catalog
from pwrbot.rules.one_rm import estimate_1rm, estimate_nrm, find_best_set

# ------------------------------------------------------------------ parsing

# Words that signal a max/RM question (used by detection regex).
_MAX_KW = r"(?:максимум|макс|рм|rm|рекорд|1rm|e1rm|е1рм)"
_ASK_KW = r"(?:какой|мой|сколько|скок|скажи|покажи|посчитай|оцени)"

_MAX_QUESTION_RE = re.compile(
    # "какой ... максимум" or "мой ... рм"
    rf"{_ASK_KW}.{{0,60}}{_MAX_KW}"
    r"|"
    # reversed: "максимум ... какой"
    rf"{_MAX_KW}.{{0,60}}{_ASK_KW}"
    r"|"
    # standalone "5рм" / "5rm"
    r"\b\d+\s*(?:рм|rm)\b"
    r"|"
    # "е1рм" / "e1rm" standalone
    r"\b[еe]1(?:рм|rm)\b"
    r"|"
    # "сколько жму/тяну/приседаю на раз" — "на раз" implies asking about 1RM
    rf"{_ASK_KW}.{{0,40}}на\s+раз\b",
    re.IGNORECASE,
)

# Patterns for extracting the number of reps.
_REPS_PATTERNS = [
    # "на 5 повторений/повторов/раз/rep" or "на 5"
    re.compile(r"на\s+(\d+)\s*(?:повтор|раз|rep)?", re.IGNORECASE),
    # "5рм" / "5rm"
    re.compile(r"(\d+)\s*(?:рм|rm)\b", re.IGNORECASE),
    # "на раз" = 1RM
    re.compile(r"на\s+раз\b", re.IGNORECASE),
]

# Words to strip when extracting the exercise name from the question.
_NOISE_WORDS = re.compile(
    r"\b(?:какой|мой|у\s+меня|сколько|скок|скажи|покажи|посчитай|оцени"
    r"|максимум|макс|рм|rm|рекорд|1rm|e1rm|е1рм"
    r"|на|повторений|повторов|повтора|повтор|раз|rep|reps"
    r"|в|по|для|упражнении|упражнение"
    r"|текущий|сейчас|сегодня)\b",
    re.IGNORECASE,
)
_CLEAN_SPACE = re.compile(r"\s+")


@dataclass(slots=True)
class MaxQuery:
    """Parsed max question: which exercise and how many reps."""

    raw_exercise: str
    reps: int  # default 1 = 1RM


def try_parse_max_question(text: str) -> MaxQuery | None:
    """Try to parse a free-form Russian text as a max/RM question.

    Returns ``MaxQuery`` if the text looks like a question about max,
    otherwise ``None`` (so the message can fall through to the workout log handler).
    """
    stripped = text.strip()
    if not stripped:
        return None

    if not _MAX_QUESTION_RE.search(stripped):
        return None

    # Extract reps
    reps = 1
    for pat in _REPS_PATTERNS:
        m = pat.search(stripped)
        if m:
            groups = m.groups()
            if groups and groups[0] is not None:
                reps = int(groups[0])
            break

    # Extract exercise name: remove question scaffolding, digits, punctuation
    exercise = _NOISE_WORDS.sub(" ", stripped)
    exercise = re.sub(r"\d+", " ", exercise)
    exercise = re.sub(r"[?!.,;:—–\-]", " ", exercise)
    exercise = _CLEAN_SPACE.sub(" ", exercise).strip()

    if not exercise:
        return None

    return MaxQuery(raw_exercise=exercise, reps=reps)


# ------------------------------------------------------------------ display

_DISPLAY_NAMES: dict[str, str] = {
    "back_squat": "присед",
    "front_squat": "фронт присед",
    "bench_press": "жим лёжа",
    "incline_bench_press": "наклонный жим",
    "deadlift": "становая",
    "sumo_deadlift": "становая сумо",
}


def _display_name(canonical_name: str) -> str:
    return _DISPLAY_NAMES.get(canonical_name, canonical_name.replace("_", " "))


def _fmt_weight(kg: float) -> str:
    if kg == int(kg):
        return f"{int(kg)}"
    return f"{kg:.1f}"


# ------------------------------------------------------------------ service


class MaxQueryService:
    """Answers free-form questions about rep maxes."""

    def __init__(self, *, catalog: Catalog, cfg: YamlConfig) -> None:
        self._catalog = catalog
        self._cfg = cfg

    async def answer(
        self,
        conn: aiosqlite.Connection,
        *,
        user_id: int,
        query: MaxQuery,
    ) -> str:
        entry = self._catalog.resolve(query.raw_exercise)
        if entry is None:
            return f"Не нашёл упражнение «{query.raw_exercise}» в каталоге."

        now_ts = int(time.time())
        day_s = 86_400
        rm_days = self._cfg.windows.rm_window_days
        history = await repo.get_workouts_in_window(
            conn,
            user_id=user_id,
            since_ts=now_ts - rm_days * day_s,
            until_ts=now_ts,
        )

        best = find_best_set(history, entry.canonical_name)
        if best is None:
            name = _display_name(entry.canonical_name)
            return f"Нет данных по «{name}» за последние {rm_days} дней."

        weight_kg, reps = best
        one_rm = estimate_1rm(weight_kg, reps)

        name = _display_name(entry.canonical_name)
        if query.reps <= 1:
            return (
                f"Расчётный 1RM для «{name}»: "
                f"~{_fmt_weight(one_rm)} кг "
                f"(на основе {_fmt_weight(weight_kg)}×{reps})"
            )

        n_rm = estimate_nrm(one_rm, query.reps)
        return (
            f"Расчётный {query.reps}RM для «{name}»: "
            f"~{_fmt_weight(n_rm)} кг "
            f"(1RM ~{_fmt_weight(one_rm)} кг, "
            f"на основе {_fmt_weight(weight_kg)}×{reps})"
        )
