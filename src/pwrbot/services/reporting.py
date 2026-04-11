"""Reporting service: per-day КПШ and intensity aggregations for the dashboard.

КПШ (количество подъёмов штанги) is defined as the sum of working reps. Working sets
are non-warmup sets. Intensity is the rep-weighted mean weight in kg over those sets:
    Σ(reps × weight_g) / Σ(reps) / 1000

Bucketing for the stacked-bar chart is driven by `target_group` from the catalog
(squat / bench / deadlift). Anything without a target_group falls into the "other"
bucket.

Filters (FilterSpec) are AND-combined; an empty list for muscle_groups or
movement_patterns means "no filter on that dimension".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import aiosqlite

from pwrbot.db import repo
from pwrbot.domain.catalog import (
    VALID_MUSCLE_GROUPS,
    Catalog,
)

# Bucket order is also the stacking order in the frontend chart.
BUCKETS: tuple[str, ...] = ("squat", "bench", "deadlift", "other")


@dataclass(slots=True)
class FilterSpec:
    muscle_groups: list[str] = field(default_factory=list)
    movement_patterns: list[str] = field(default_factory=list)
    target_only: bool = False


@dataclass(slots=True)
class DashboardData:
    days: list[date]
    kpsh_by_bucket: dict[str, list[int]]
    intensity_kg: list[float | None]
    kpsh_by_muscle: dict[str, int]
    kpsh_by_pattern: dict[str, int]
    total_workouts: int
    total_kpsh: int
    avg_intensity_kg: float | None


def _ts_to_date(ts: int) -> date:
    return datetime.fromtimestamp(ts, tz=UTC).date()


def _daterange(start: date, end: date) -> list[date]:
    if end < start:
        return []
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _bucket_for(target_group: str | None) -> str:
    return target_group if target_group in ("squat", "bench", "deadlift") else "other"


async def build_dashboard(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    since_ts: int,
    until_ts: int,
    filter_spec: FilterSpec,
    catalog: Catalog,
) -> DashboardData:
    """Aggregate per-day КПШ and intensity within [since_ts, until_ts].

    The output `days` axis is contiguous (every UTC day in the window) so the
    frontend can render gaps for empty days. Empty days have kpsh=0 across all
    buckets and intensity=None.
    """
    workouts = await repo.get_workouts_in_window(
        conn, user_id=user_id, since_ts=since_ts, until_ts=until_ts
    )

    days = _daterange(_ts_to_date(since_ts), _ts_to_date(until_ts))
    day_index: dict[date, int] = {d: i for i, d in enumerate(days)}
    n = len(days)

    kpsh_by_bucket: dict[str, list[int]] = {b: [0] * n for b in BUCKETS}
    rep_w_sum_per_day = [0] * n  # Σ(reps × weight_g)
    rep_sum_per_day = [0] * n  # Σ(reps)
    kpsh_by_muscle: dict[str, int] = {m: 0 for m in VALID_MUSCLE_GROUPS}
    kpsh_by_pattern: dict[str, int] = defaultdict(int)
    contributed_workout_ids: set[int] = set()

    muscle_filter = set(filter_spec.muscle_groups)
    pattern_filter = set(filter_spec.movement_patterns)

    for w in workouts:
        d = _ts_to_date(w.performed_at)
        if d not in day_index:
            continue  # outside the contiguous window (defensive)
        idx = day_index[d]

        for ex in w.exercises:
            entry = (
                catalog.by_canonical(ex.canonical_name) if ex.canonical_name else None
            )
            target_group = entry.target_group if entry else None
            muscle_group = entry.muscle_group if entry else None
            movement_pattern = (
                entry.movement_pattern if entry else ex.movement_pattern
            )

            # Apply filters
            if filter_spec.target_only and target_group is None:
                continue
            if muscle_filter and (muscle_group not in muscle_filter):
                continue
            if pattern_filter and (movement_pattern not in pattern_filter):
                continue

            bucket = _bucket_for(target_group)

            for s in ex.sets:
                if s.is_warmup or s.reps <= 0:
                    continue
                kpsh_by_bucket[bucket][idx] += s.reps
                rep_w_sum_per_day[idx] += s.reps * s.weight_g
                rep_sum_per_day[idx] += s.reps
                if muscle_group is not None:
                    kpsh_by_muscle[muscle_group] += s.reps
                if movement_pattern:
                    kpsh_by_pattern[movement_pattern] += s.reps
                contributed_workout_ids.add(w.id)

    intensity_kg: list[float | None] = []
    for i in range(n):
        if rep_sum_per_day[i] > 0:
            intensity_kg.append(rep_w_sum_per_day[i] / rep_sum_per_day[i] / 1000.0)
        else:
            intensity_kg.append(None)

    total_kpsh = sum(sum(v) for v in kpsh_by_bucket.values())
    total_rep_w = sum(rep_w_sum_per_day)
    total_reps = sum(rep_sum_per_day)
    avg_intensity_kg = (
        total_rep_w / total_reps / 1000.0 if total_reps > 0 else None
    )

    return DashboardData(
        days=days,
        kpsh_by_bucket=kpsh_by_bucket,
        intensity_kg=intensity_kg,
        kpsh_by_muscle=kpsh_by_muscle,
        kpsh_by_pattern=dict(kpsh_by_pattern),
        total_workouts=len(contributed_workout_ids),
        total_kpsh=total_kpsh,
        avg_intensity_kg=avg_intensity_kg,
    )
