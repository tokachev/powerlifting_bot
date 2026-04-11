"""Imbalance and recovery-risk flag detection.

Produces a list of dict flags (kind, pattern, details) ready to be JSON-serialized
into analysis_snapshots.flags_json.
"""

from __future__ import annotations

from pwrbot.config import Thresholds
from pwrbot.rules.balance import BalanceMetrics
from pwrbot.rules.volume import VolumeMetrics


def _ratio_outside_tolerance(
    ratio: float | None, target: float, tolerance: float
) -> bool:
    if ratio is None:
        return False
    if ratio == float("inf"):
        return True
    lo = target * (1 - tolerance)
    hi = target * (1 + tolerance)
    return ratio < lo or ratio > hi


def imbalance_flags(
    balance: BalanceMetrics, thresholds: Thresholds
) -> list[dict]:
    out: list[dict] = []
    b = thresholds.balance

    # push/pull
    smaller_pp = min(balance.push_hard_sets, balance.pull_hard_sets)
    if (
        _ratio_outside_tolerance(balance.push_pull_ratio, b.push_pull_target, b.tolerance)
        and smaller_pp >= b.min_hard_sets_for_flag
    ):
        out.append(
            {
                "kind": "imbalance",
                "axis": "push_pull",
                "ratio": balance.push_pull_ratio,
                "target": b.push_pull_target,
                "push_hard_sets": balance.push_hard_sets,
                "pull_hard_sets": balance.pull_hard_sets,
            }
        )

    # squat/hinge
    smaller_sh = min(balance.squat_hard_sets, balance.hinge_hard_sets)
    if (
        _ratio_outside_tolerance(balance.squat_hinge_ratio, b.squat_hinge_target, b.tolerance)
        and smaller_sh >= b.min_hard_sets_for_flag
    ):
        out.append(
            {
                "kind": "imbalance",
                "axis": "squat_hinge",
                "ratio": balance.squat_hinge_ratio,
                "target": b.squat_hinge_target,
                "squat_hard_sets": balance.squat_hard_sets,
                "hinge_hard_sets": balance.hinge_hard_sets,
            }
        )

    return out


def recovery_flags(
    *,
    short_window_metrics: VolumeMetrics,
    previous_short_window_metrics: VolumeMetrics | None,
    thresholds: Thresholds,
) -> list[dict]:
    """Recovery risk = short-window hard sets exceeding the per-pattern cap OR
    tonnage spike > 1.5× vs previous short window."""
    out: list[dict] = []
    caps = thresholds.recovery.max_hard_sets_7d

    for pattern, cap in caps.items():
        hard = short_window_metrics.hard_sets_by_pattern.get(pattern, 0)
        if hard > cap:
            out.append(
                {
                    "kind": "recovery_risk",
                    "pattern": pattern,
                    "hard_sets_7d": hard,
                    "cap": cap,
                }
            )

    if previous_short_window_metrics is not None:
        prev_tonnage = previous_short_window_metrics.total_tonnage_kg
        curr_tonnage = short_window_metrics.total_tonnage_kg
        if prev_tonnage > 0 and curr_tonnage / prev_tonnage > thresholds.recovery.tonnage_spike_ratio:
            out.append(
                {
                    "kind": "recovery_risk",
                    "subtype": "tonnage_spike",
                    "current_tonnage_kg": curr_tonnage,
                    "previous_tonnage_kg": prev_tonnage,
                    "ratio": round(curr_tonnage / prev_tonnage, 2),
                    "ratio_threshold": thresholds.recovery.tonnage_spike_ratio,
                }
            )

    return out
