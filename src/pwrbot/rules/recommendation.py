"""Deterministic next-workout recommendations from existing rule outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pwrbot.config import Thresholds

_PATTERN_LABELS: dict[str, str] = {
    "squat": "squat",
    "hinge": "hinge",
    "push": "push",
    "pull": "pull",
    "recovery": "восстановительная",
}

_DEFAULT_ORDER = ("squat", "hinge", "push", "pull")


@dataclass(slots=True)
class NextWorkoutRecommendation:
    focus_pattern: str
    title: str
    rationale: list[str] = field(default_factory=list)
    caution_patterns: list[str] = field(default_factory=list)


def _pattern_label(pattern: str) -> str:
    return _PATTERN_LABELS.get(pattern, pattern)


def _hard_sets_7d(metrics: dict[str, Any]) -> dict[str, int]:
    raw = metrics.get("last_7d", {}).get("hard_sets_by_pattern", {})
    if not isinstance(raw, dict):
        return {}
    return {str(k): int(v) for k, v in raw.items()}


def _blocked_patterns(
    *,
    hard_sets: dict[str, int],
    flags: list[dict[str, Any]],
    thresholds: Thresholds,
) -> set[str]:
    blocked: set[str] = set()
    caps = thresholds.recovery.max_hard_sets_7d
    for pattern, cap in caps.items():
        if hard_sets.get(pattern, 0) >= cap:
            blocked.add(pattern)
    for flag in flags:
        if flag.get("kind") == "recovery_risk" and flag.get("pattern"):
            blocked.add(str(flag["pattern"]))
    return blocked


def _imbalance_candidates(
    metrics: dict[str, Any],
    flags: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    balance = metrics.get("balance_28d", {})
    candidates: list[tuple[str, str]] = []

    for flag in flags:
        if flag.get("kind") != "imbalance":
            continue
        axis = flag.get("axis")
        ratio = flag.get("ratio")
        target = flag.get("target", 1.0)

        if axis == "push_pull":
            push = int(balance.get("push_hard_sets", flag.get("push_hard_sets", 0)) or 0)
            pull = int(balance.get("pull_hard_sets", flag.get("pull_hard_sets", 0)) or 0)
            if ratio == float("inf") or (ratio is not None and ratio > target) or push > pull:
                candidates.append(("pull", "сбалансировать избыток push относительно pull"))
            else:
                candidates.append(("push", "сбалансировать недостаток push относительно pull"))

        if axis == "squat_hinge":
            squat = int(balance.get("squat_hard_sets", flag.get("squat_hard_sets", 0)) or 0)
            hinge = int(balance.get("hinge_hard_sets", flag.get("hinge_hard_sets", 0)) or 0)
            if ratio == float("inf") or (ratio is not None and ratio > target) or squat > hinge:
                candidates.append(("hinge", "сбалансировать избыток squat относительно hinge"))
            else:
                candidates.append(("squat", "сбалансировать недостаток squat относительно hinge"))

    return candidates


def recommend_next_workout(
    *,
    metrics: dict[str, Any],
    flags: list[dict[str, Any]],
    thresholds: Thresholds,
) -> NextWorkoutRecommendation:
    """Choose the next workout focus deterministically.

    Priority order:
    1. Prefer an unblocked pattern that corrects a 28-day imbalance flag.
    2. Otherwise choose the pattern with the lowest recent hard-set usage relative
       to its 7-day cap.
    3. If every tracked pattern is at recovery risk, recommend a recovery session.
    """

    hard_sets = _hard_sets_7d(metrics)
    caps = thresholds.recovery.max_hard_sets_7d
    patterns = [p for p in _DEFAULT_ORDER if p in caps]
    blocked = _blocked_patterns(hard_sets=hard_sets, flags=flags, thresholds=thresholds)

    for pattern, reason in _imbalance_candidates(metrics, flags):
        if pattern not in blocked and pattern in patterns:
            return NextWorkoutRecommendation(
                focus_pattern=pattern,
                title=f"Следующая тренировка: {_pattern_label(pattern)}",
                rationale=[
                    reason,
                    f"за 7 дней: {hard_sets.get(pattern, 0)}/{caps[pattern]} hard-сетов",
                ],
                caution_patterns=sorted(blocked),
            )

    available = [p for p in patterns if p not in blocked]
    if not available:
        return NextWorkoutRecommendation(
            focus_pattern="recovery",
            title="Следующая тренировка: восстановительная",
            rationale=["все основные паттерны упёрлись в 7-дневные лимиты или recovery-risk"],
            caution_patterns=sorted(blocked),
        )

    def usage_key(pattern: str) -> tuple[float, int, int]:
        cap = caps[pattern]
        hard = hard_sets.get(pattern, 0)
        order_index = patterns.index(pattern)
        return (hard / cap if cap > 0 else 1.0, hard, order_index)

    focus = min(available, key=usage_key)
    return NextWorkoutRecommendation(
        focus_pattern=focus,
        title=f"Следующая тренировка: {_pattern_label(focus)}",
        rationale=[
            "минимальная недавняя нагрузка относительно недельного лимита",
            f"за 7 дней: {hard_sets.get(focus, 0)}/{caps[focus]} hard-сетов",
        ],
        caution_patterns=sorted(blocked),
    )
