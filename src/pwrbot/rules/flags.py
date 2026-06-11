"""Imbalance, recovery-risk and progress flag detection.

Produces a list of dict flags (kind, pattern, details) ready to be JSON-serialized
into analysis_snapshots.flags_json.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pwrbot.config import Thresholds
from pwrbot.db.repo import WorkoutRow
from pwrbot.metrics.rep_distribution import compute_rep_distribution
from pwrbot.rules.balance import BalanceMetrics
from pwrbot.rules.volume import VolumeMetrics

if TYPE_CHECKING:
    from pwrbot.metrics.e1rm_trend import E1RMPoint


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


def stagnation_flags(
    points: list[E1RMPoint],
    *,
    now_ts: int,
    thresholds: Thresholds,
) -> list[dict]:
    """Stagnation = the best e1RM of the window was set long ago and hasn't been
    beaten (within tolerance) since, despite enough sessions of the exercise.

    `points` come from metrics.e1rm_trend.compute_e1rm_trend over the 28d history.
    """
    p = thresholds.progress
    out: list[dict] = []

    by_name: dict[str, list[E1RMPoint]] = {}
    for point in points:
        by_name.setdefault(point.canonical_name, []).append(point)

    today = datetime.fromtimestamp(now_ts, tz=UTC).date()
    for name, pts in by_name.items():
        if len(pts) < p.stagnation_min_sessions:
            continue
        pts = sorted(pts, key=lambda x: x.date)
        best = max(pts, key=lambda x: x.estimated_1rm_kg)
        days_since_best = (today - best.date).days
        if days_since_best < p.stagnation_min_days_since_best:
            continue
        later = [x for x in pts if x.date > best.date]
        if not later:
            continue
        best_after = max(x.estimated_1rm_kg for x in later)
        if best_after >= best.estimated_1rm_kg + p.stagnation_tolerance_kg:
            continue
        out.append(
            {
                "kind": "stagnation",
                "exercise": name,
                "sessions": len(pts),
                "best_e1rm_kg": round(best.estimated_1rm_kg, 1),
                "best_date": best.date.isoformat(),
                "days_since_best": days_since_best,
                "last_e1rm_kg": round(pts[-1].estimated_1rm_kg, 1),
            }
        )

    return out


def frequency_drop_flags(
    workouts_28d: list[WorkoutRow],
    *,
    now_ts: int,
    thresholds: Thresholds,
) -> list[dict]:
    """Flag when the last 7 days had clearly fewer workouts than the user's
    own average over the previous three weeks."""
    p = thresholds.progress
    day_s = 86_400
    week_ago = now_ts - 7 * day_s

    current_days = {w.performed_at // day_s for w in workouts_28d if w.performed_at >= week_ago}
    prior_days = {w.performed_at // day_s for w in workouts_28d if w.performed_at < week_ago}
    if not prior_days:
        return []
    prior_weekly_avg = len(prior_days) / 3.0
    if prior_weekly_avg < 1.0:
        return []
    if len(current_days) >= prior_weekly_avg * p.frequency_drop_fraction:
        return []
    return [
        {
            "kind": "frequency_drop",
            "workouts_7d": len(current_days),
            "prior_weekly_avg": round(prior_weekly_avg, 1),
        }
    ]


def neglected_pattern_flags(
    *,
    recent_metrics: VolumeMetrics,
    prior_metrics: VolumeMetrics,
    thresholds: Thresholds,
) -> list[dict]:
    """Flag movement patterns that were trained in the prior 14 days but have
    zero working sets in the most recent 14 days."""
    out: list[dict] = []
    for pattern, prior_sets in prior_metrics.working_sets_by_pattern.items():
        if pattern == "accessory":
            continue
        if prior_sets <= 0:
            continue
        if recent_metrics.working_sets_by_pattern.get(pattern, 0) > 0:
            continue
        out.append(
            {
                "kind": "neglected_pattern",
                "pattern": pattern,
                "prior_working_sets": prior_sets,
                "days": thresholds.progress.neglected_pattern_days,
            }
        )
    return out


def rep_monotony_flags(
    workouts_28d: list[WorkoutRow],
    *,
    thresholds: Thresholds,
) -> list[dict]:
    """Flag when nearly all working sets over 28d fall into one rep-range bucket."""
    p = thresholds.progress
    buckets = compute_rep_distribution(workouts_28d)
    total_sets = sum(b.set_count for b in buckets)
    if total_sets < p.rep_monotony_min_sets:
        return []
    top = max(buckets, key=lambda b: b.set_count)
    if top.set_count / total_sets < p.rep_monotony_fraction:
        return []
    return [
        {
            "kind": "rep_monotony",
            "rep_range": top.rep_range,
            "sets_in_range": top.set_count,
            "total_sets": total_sets,
            "share": round(top.set_count / total_sets, 2),
        }
    ]
