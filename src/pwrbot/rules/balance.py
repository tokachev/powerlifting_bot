"""Movement-pattern balance ratios derived from VolumeMetrics."""

from __future__ import annotations

from dataclasses import dataclass

from pwrbot.rules.volume import VolumeMetrics


@dataclass(slots=True)
class BalanceMetrics:
    push_hard_sets: int
    pull_hard_sets: int
    squat_hard_sets: int
    hinge_hard_sets: int
    push_pull_ratio: float | None      # push / pull, None if either is 0
    squat_hinge_ratio: float | None


def _ratio(a: int, b: int) -> float | None:
    if a == 0 and b == 0:
        return None
    if b == 0:
        return float("inf")
    return a / b


def compute(metrics: VolumeMetrics) -> BalanceMetrics:
    hard = metrics.hard_sets_by_pattern
    push = hard.get("push", 0)
    pull = hard.get("pull", 0)
    squat = hard.get("squat", 0)
    hinge = hard.get("hinge", 0)
    return BalanceMetrics(
        push_hard_sets=push,
        pull_hard_sets=pull,
        squat_hard_sets=squat,
        hinge_hard_sets=hinge,
        push_pull_ratio=_ratio(push, pull),
        squat_hinge_ratio=_ratio(squat, hinge),
    )
