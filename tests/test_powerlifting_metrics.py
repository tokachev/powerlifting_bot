"""Tests for powerlifting metrics: Wilks, DOTS, IPF GL, ACWR, rep_max_table,
plus Big 3 target_group matching + variant coefficient rollup."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from pwrbot.db.repo import ExerciseRow, SetRow, WorkoutRow
from pwrbot.domain.catalog import Catalog, load_catalog
from pwrbot.metrics.powerlifting import (
    acwr_from_daily_tonnage,
    best_weight_by_min_reps,
    compute_accessories_overview,
    compute_big3_summary,
    compute_lift_weekly,
    compute_recent_sessions,
    dots_score,
    ipf_gl_points,
    rep_max_table,
    wilks_score,
)
from pwrbot.rules.one_rm import estimate_1rm

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog(REPO_ROOT / "config" / "exercises.yaml")


def _set(reps: int, kg: float, *, warmup: bool = False, idx: int = 1) -> SetRow:
    return SetRow(
        reps=reps, weight_g=int(kg * 1000), rpe=None, is_warmup=warmup, set_index=idx,
    )


def _ex(canonical: str, pattern: str, sets: list[SetRow]) -> ExerciseRow:
    return ExerciseRow(
        position=1, raw_name=canonical, canonical_name=canonical,
        movement_pattern=pattern, sets=sets,
    )


def _workout(d: date, exercises: list[ExerciseRow]) -> WorkoutRow:
    ts = int(datetime(d.year, d.month, d.day, 12, tzinfo=UTC).timestamp())
    return WorkoutRow(
        id=1, user_id=1, performed_at=ts, logged_at=ts,
        source_text="", notes=None, exercises=exercises,
    )


def test_wilks_zero_on_invalid_inputs():
    assert wilks_score(0, 85) == 0.0
    assert wilks_score(500, 0) == 0.0
    assert wilks_score(-1, 80) == 0.0


def test_wilks_male_reasonable():
    v = wilks_score(675, 85, is_female=False)
    assert 400 <= v <= 450, v


def test_wilks_female_reasonable():
    v = wilks_score(400, 60, is_female=True)
    assert 350 <= v <= 500, v


def test_dots_reasonable():
    v = dots_score(675, 85)
    assert 400 <= v <= 480, v


def test_ipf_gl_reasonable():
    v = ipf_gl_points(675, 85)
    assert 80 <= v <= 105, v


def test_rep_max_identity_at_1():
    table = rep_max_table(200.0)
    assert table[1] == 200.0


def test_rep_max_monotonic_decreasing():
    table = rep_max_table(200.0)
    vals = [table[r] for r in (1, 2, 3, 5, 8, 10)]
    assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))


def test_rep_max_zero_input():
    assert rep_max_table(0.0) == {1: 0.0, 2: 0.0, 3: 0.0, 5: 0.0, 8: 0.0, 10: 0.0}


def test_rep_max_symmetric_with_estimate_1rm():
    """200kg x 3 squat → 1RM via Brzycki. Reversing via rep_max_table[3] must give 200."""
    one_rm = estimate_1rm(200.0, 3)
    table = rep_max_table(one_rm)
    assert table[3] == 200.0
    # 2RM must be >= 3RM (more reps → lighter)
    assert table[2] >= table[3]


def test_rep_max_with_floor_raises_below_actual(catalog: Catalog):
    """User did 200x3 squat yesterday. 2RM estimate would be below 200 without floor.
    With floor_by_min_reps, the table must never drop below what was actually lifted.
    """
    today = date(2026, 4, 19)
    workouts = [_workout(today - timedelta(days=1), [
        _ex("back_squat", "squat", [_set(3, 200)]),
    ])]
    floor = best_weight_by_min_reps(
        workouts, target_group="squat", catalog=catalog,
        since=today - timedelta(days=27), until=today,
    )
    one_rm = estimate_1rm(200.0, 3)
    table = rep_max_table(one_rm, floor_by_min_reps=floor)
    assert table[3] == 200.0   # exactly what was lifted
    assert table[2] >= 200.0   # can't be below a heavier set he did for more reps
    assert table[1] >= 200.0


def test_best_weight_by_min_reps_primary_lift(catalog: Catalog):
    today = date(2026, 4, 19)
    workouts = [_workout(today - timedelta(days=1), [
        _ex("back_squat", "squat", [_set(5, 150), _set(3, 180)]),
    ])]
    out = best_weight_by_min_reps(
        workouts, target_group="squat", catalog=catalog,
        since=today - timedelta(days=27), until=today,
    )
    # reps >= 1: max = 180; >= 2: 180; >= 3: 180; >= 5: 150; >= 8: 0; >= 10: 0
    assert out[1] == 180.0
    assert out[2] == 180.0
    assert out[3] == 180.0
    assert out[5] == 150.0
    assert out[8] == 0.0
    assert out[10] == 0.0


def test_best_weight_by_min_reps_variant_applies_coefficient(catalog: Catalog):
    """front_squat 100x5 with coef 0.85 → primary-lift equivalent ≈ 117.6kg for R<=5."""
    today = date(2026, 4, 19)
    workouts = [_workout(today - timedelta(days=1), [
        _ex("front_squat", "squat", [_set(5, 100)]),
    ])]
    out = best_weight_by_min_reps(
        workouts, target_group="squat", catalog=catalog,
        since=today - timedelta(days=27), until=today,
    )
    assert abs(out[5] - (100 / 0.85)) < 0.1
    assert abs(out[3] - (100 / 0.85)) < 0.1
    assert out[8] == 0.0


def test_best_weight_by_min_reps_skips_warmup_and_out_of_window(catalog: Catalog):
    today = date(2026, 4, 19)
    workouts = [
        _workout(today - timedelta(days=1), [
            _ex("back_squat", "squat", [
                _set(3, 200, warmup=True),  # skip warmup
                _set(5, 100),
            ]),
        ]),
        _workout(today - timedelta(days=40), [  # out of window
            _ex("back_squat", "squat", [_set(3, 220)]),
        ]),
    ]
    out = best_weight_by_min_reps(
        workouts, target_group="squat", catalog=catalog,
        since=today - timedelta(days=27), until=today,
    )
    assert out[1] == 100.0
    assert out[3] == 100.0  # 5-rep set qualifies (5 >= 3)
    assert out[5] == 100.0
    assert out[8] == 0.0   # no set with reps >= 8


def test_acwr_sweet_spot():
    today = date(2026, 4, 18)
    daily = {today - timedelta(days=i): 1000.0 for i in range(28)}
    # Acute = 7000, chronic_avg = 28000/4 = 7000, ratio=1.0
    r = acwr_from_daily_tonnage(daily, today)
    assert r.ratio == 1.0
    assert r.risk_zone == "sweet"


def test_acwr_danger():
    today = date(2026, 4, 18)
    # Spike week
    daily = {today - timedelta(days=i): (5000.0 if i < 7 else 500.0) for i in range(28)}
    r = acwr_from_daily_tonnage(daily, today)
    assert r.ratio > 1.5
    assert r.risk_zone == "danger"


def test_acwr_empty():
    r = acwr_from_daily_tonnage({}, date(2026, 4, 18))
    assert r.ratio == 0.0
    assert r.risk_zone == "low"


# ========================================== Big 3 target_group + coefficient


def test_big3_summary_counts_sumo_as_deadlift(catalog):
    today = date(2026, 4, 18)
    workouts = [
        _workout(
            today - timedelta(days=3),
            [_ex("sumo_deadlift", "hinge", [_set(5, 200.0)])],
        )
    ]
    big3 = compute_big3_summary(
        workouts, today=today, bodyweight_kg=None,
        pr_by_lift={}, next_meet_targets_kg={}, catalog=catalog,
    )
    dl = next(b for b in big3 if b.lift == "deadlift")
    # sumo coefficient is 1.0: estimate_1rm(200, 5) ≈ 225.0 (Brzycki)
    assert dl.current_e1rm_kg > 220.0
    assert dl.sessions_28d == 1


def test_big3_summary_applies_variant_coefficient(catalog):
    today = date(2026, 4, 18)
    # front_squat 100 × 5 → Brzycki e1RM = 112.5, scaled by 1/0.85 ≈ 132.4
    workouts = [
        _workout(
            today - timedelta(days=5),
            [_ex("front_squat", "squat", [_set(5, 100.0)])],
        )
    ]
    big3 = compute_big3_summary(
        workouts, today=today, bodyweight_kg=None,
        pr_by_lift={}, next_meet_targets_kg={}, catalog=catalog,
    )
    sq = next(b for b in big3 if b.lift == "squat")
    assert 130.0 < sq.current_e1rm_kg < 135.0


def test_big3_summary_prefers_max_across_variants(catalog):
    today = date(2026, 4, 18)
    # Direct back_squat gives a higher equivalent than front_squat here.
    workouts = [
        _workout(
            today - timedelta(days=5),
            [
                _ex("front_squat", "squat", [_set(5, 100.0)]),  # → ~132 primary
                _ex("back_squat", "squat", [_set(3, 180.0)]),   # Brzycki → ~190.6
            ],
        )
    ]
    big3 = compute_big3_summary(
        workouts, today=today, bodyweight_kg=None,
        pr_by_lift={}, next_meet_targets_kg={}, catalog=catalog,
    )
    sq = next(b for b in big3 if b.lift == "squat")
    assert sq.current_e1rm_kg > 185.0


def test_big3_summary_warmups_excluded(catalog):
    today = date(2026, 4, 18)
    workouts = [
        _workout(
            today - timedelta(days=1),
            [_ex("sumo_deadlift", "hinge", [_set(5, 200.0, warmup=True)])],
        )
    ]
    big3 = compute_big3_summary(
        workouts, today=today, bodyweight_kg=None,
        pr_by_lift={}, next_meet_targets_kg={}, catalog=catalog,
    )
    dl = next(b for b in big3 if b.lift == "deadlift")
    assert dl.current_e1rm_kg == 0.0


def test_big3_summary_empty_when_no_matching_target_group(catalog):
    today = date(2026, 4, 18)
    # romanian_deadlift has no target_group → must not count for Big 3.
    workouts = [
        _workout(
            today - timedelta(days=2),
            [_ex("romanian_deadlift", "hinge", [_set(5, 150.0)])],
        )
    ]
    big3 = compute_big3_summary(
        workouts, today=today, bodyweight_kg=None,
        pr_by_lift={}, next_meet_targets_kg={}, catalog=catalog,
    )
    dl = next(b for b in big3 if b.lift == "deadlift")
    assert dl.current_e1rm_kg == 0.0
    assert dl.sessions_28d == 0


def test_compute_lift_weekly_scales_variant_tonnage(catalog):
    today = date(2026, 4, 18)
    # Same week: front_squat 100×5 (coef 0.85) → scaled weight 100/0.85 ≈ 117.6
    workouts = [
        _workout(
            today - timedelta(days=1),
            [_ex("front_squat", "squat", [_set(5, 100.0)])],
        )
    ]
    series = compute_lift_weekly(
        workouts, target_group="squat", catalog=catalog, weeks=4, today=today,
    )
    assert len(series) == 1
    # e1rm in primary-lift units: Brzycki(100,5)=112.5 / 0.85 ≈ 132.4
    assert 130.0 < series[0].e1rm_kg < 135.0
    # tonnage also in primary-lift units: 5 × (100/0.85) ≈ 588.2
    assert series[0].tonnage_kg > 580.0


def test_accessories_excludes_all_target_group_variants(catalog):
    today = date(2026, 4, 18)
    workouts = [
        _workout(
            today - timedelta(days=2),
            [
                _ex("incline_bench_press", "push", [_set(5, 80.0)]),  # bench variant
                _ex("sumo_deadlift", "hinge", [_set(5, 200.0)]),      # deadlift variant
                _ex("barbell_row", "pull", [_set(5, 100.0)]),         # real accessory
            ],
        )
    ]
    acc = compute_accessories_overview(workouts, today=today, catalog=catalog)
    names = {a.canonical_name for a in acc}
    assert "incline_bench_press" not in names
    assert "sumo_deadlift" not in names
    assert "barbell_row" in names


def test_recent_session_focus_from_target_group(catalog):
    today = date(2026, 4, 18)
    workouts = [
        _workout(
            today,
            [_ex("sumo_deadlift", "hinge", [_set(5, 200.0), _set(5, 200.0)])],
        )
    ]
    rs = compute_recent_sessions(workouts, limit=7, catalog=catalog)
    assert len(rs) == 1
    assert rs[0].focus == "deadlift"
