"""Tests for powerlifting metrics: Wilks, DOTS, IPF GL, ACWR, rep_max_table."""

from __future__ import annotations

from datetime import date, timedelta

from pwrbot.metrics.powerlifting import (
    acwr_from_daily_tonnage,
    dots_score,
    ipf_gl_points,
    rep_max_table,
    wilks_score,
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
