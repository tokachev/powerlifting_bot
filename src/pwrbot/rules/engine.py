"""Top-level rules engine. Takes WorkoutRow lists, returns a snapshot dict.

The engine computes:
- VolumeMetrics for the analysis window
- BalanceMetrics derived from VolumeMetrics
- Flags: imbalance (on the long-window balance, so a single-session blip doesn't fire)
  and recovery_risk (on the short window vs the previous short window)
"""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from pwrbot.config import YamlConfig
from pwrbot.db.repo import WorkoutRow
from pwrbot.rules import balance, flags, volume


def _split_by_time(
    workouts: list[WorkoutRow], since_ts: int, until_ts: int
) -> list[WorkoutRow]:
    return [w for w in workouts if since_ts <= w.performed_at <= until_ts]


def run(
    *,
    all_workouts_28d: list[WorkoutRow],
    window_days: int,
    cfg: YamlConfig,
    now_ts: int | None = None,
) -> dict[str, Any]:
    """Run the full engine for a requested window_days view.

    `all_workouts_28d` MUST contain the last 28 days of workouts — the engine uses
    the full span for rolling-best intensity estimation and for tonnage-spike detection
    (previous short window). It then slices down to the actual `window_days`.
    """
    now = int(time.time()) if now_ts is None else now_ts
    day_s = 86_400

    # Slices
    short_days = cfg.windows.short_days
    current_short = _split_by_time(all_workouts_28d, now - short_days * day_s, now)
    previous_short = _split_by_time(
        all_workouts_28d,
        now - 2 * short_days * day_s,
        now - short_days * day_s - 1,
    )
    long_window = _split_by_time(all_workouts_28d, now - cfg.windows.long_days * day_s, now)

    analysis_workouts = _split_by_time(all_workouts_28d, now - window_days * day_s, now)

    # Volume: use long_window as history for rolling-best (intensity_fraction fallback)
    window_volume = volume.compute(
        analysis_workouts, cfg.thresholds, history_for_intensity=long_window
    )
    short_volume = volume.compute(
        current_short, cfg.thresholds, history_for_intensity=long_window
    )
    prev_short_volume = volume.compute(
        previous_short, cfg.thresholds, history_for_intensity=long_window
    )
    long_volume = volume.compute(
        long_window, cfg.thresholds, history_for_intensity=long_window
    )

    # Balance: use long window — more stable than a single session
    long_balance = balance.compute(long_volume)

    # 14d halves of the long window for neglected-pattern detection
    neglect_days = cfg.thresholds.progress.neglected_pattern_days
    recent_half = volume.compute(
        _split_by_time(all_workouts_28d, now - neglect_days * day_s, now),
        cfg.thresholds,
        history_for_intensity=long_window,
    )
    prior_half = volume.compute(
        _split_by_time(
            all_workouts_28d,
            now - 2 * neglect_days * day_s,
            now - neglect_days * day_s - 1,
        ),
        cfg.thresholds,
        history_for_intensity=long_window,
    )

    # Flags
    imbalance = flags.imbalance_flags(long_balance, cfg.thresholds)
    recovery = flags.recovery_flags(
        short_window_metrics=short_volume,
        previous_short_window_metrics=prev_short_volume,
        thresholds=cfg.thresholds,
    )
    frequency = flags.frequency_drop_flags(
        all_workouts_28d, now_ts=now, thresholds=cfg.thresholds
    )
    neglected = flags.neglected_pattern_flags(
        recent_metrics=recent_half,
        prior_metrics=prior_half,
        thresholds=cfg.thresholds,
    )
    monotony = flags.rep_monotony_flags(all_workouts_28d, thresholds=cfg.thresholds)

    metrics: dict[str, Any] = {
        "window_days": window_days,
        "window": asdict(window_volume),
        "last_7d": asdict(short_volume),
        "prev_7d": asdict(prev_short_volume),
        "delta_7d": _week_over_week_delta(short_volume, prev_short_volume),
        "long_28d": asdict(long_volume),
        "balance_28d": {
            "push_hard_sets": long_balance.push_hard_sets,
            "pull_hard_sets": long_balance.pull_hard_sets,
            "squat_hard_sets": long_balance.squat_hard_sets,
            "hinge_hard_sets": long_balance.hinge_hard_sets,
            "push_pull_ratio": long_balance.push_pull_ratio,
            "squat_hinge_ratio": long_balance.squat_hinge_ratio,
        },
    }

    return {
        "window_days": window_days,
        "computed_at": now,
        "metrics": metrics,
        "flags": imbalance + recovery + frequency + neglected + monotony,
    }


def _week_over_week_delta(
    current: volume.VolumeMetrics, previous: volume.VolumeMetrics
) -> dict[str, Any]:
    """Compare the last 7 days against the 7 days before them."""
    tonnage_delta = round(current.total_tonnage_kg - previous.total_tonnage_kg, 1)
    tonnage_pct: float | None = None
    if previous.total_tonnage_kg > 0:
        tonnage_pct = round(tonnage_delta / previous.total_tonnage_kg * 100, 1)
    patterns = set(current.hard_sets_by_pattern) | set(previous.hard_sets_by_pattern)
    return {
        "tonnage_kg": tonnage_delta,
        "tonnage_pct": tonnage_pct,
        "hard_sets": current.total_hard_sets - previous.total_hard_sets,
        "hard_sets_by_pattern": {
            p: current.hard_sets_by_pattern.get(p, 0) - previous.hard_sets_by_pattern.get(p, 0)
            for p in sorted(patterns)
        },
    }
