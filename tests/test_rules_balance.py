from __future__ import annotations

from pwrbot.rules import balance
from pwrbot.rules.volume import VolumeMetrics


def test_balance_computes_ratios() -> None:
    m = VolumeMetrics(
        total_working_sets=20,
        total_hard_sets=16,
        total_tonnage_kg=5000,
        hard_sets_by_pattern={"push": 8, "pull": 4, "squat": 6, "hinge": 6},
        working_sets_by_pattern={},
        tonnage_by_pattern_kg={},
    )
    b = balance.compute(m)
    assert b.push_hard_sets == 8
    assert b.pull_hard_sets == 4
    assert b.push_pull_ratio == 2.0
    assert b.squat_hinge_ratio == 1.0


def test_balance_none_when_both_zero() -> None:
    m = VolumeMetrics(hard_sets_by_pattern={"push": 0, "pull": 0})
    b = balance.compute(m)
    assert b.push_pull_ratio is None


def test_balance_inf_when_denominator_zero() -> None:
    m = VolumeMetrics(hard_sets_by_pattern={"push": 5, "pull": 0})
    b = balance.compute(m)
    assert b.push_pull_ratio == float("inf")
