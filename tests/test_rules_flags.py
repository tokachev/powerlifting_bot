from __future__ import annotations

from pwrbot.rules import flags
from pwrbot.rules.balance import BalanceMetrics
from pwrbot.rules.volume import VolumeMetrics


def test_imbalance_flag_fires_outside_tolerance(yaml_config) -> None:
    b = BalanceMetrics(
        push_hard_sets=12,
        pull_hard_sets=5,
        squat_hard_sets=6,
        hinge_hard_sets=6,
        push_pull_ratio=12 / 5,   # 2.4, way above 1.3 ceiling
        squat_hinge_ratio=1.0,
    )
    result = flags.imbalance_flags(b, yaml_config.thresholds)
    kinds = [f["axis"] for f in result]
    assert "push_pull" in kinds
    assert "squat_hinge" not in kinds


def test_imbalance_flag_suppressed_when_smaller_side_below_min(yaml_config) -> None:
    """Single-session blip — smaller side (2 sets) below the 5-set minimum → no flag."""
    b = BalanceMetrics(
        push_hard_sets=10,
        pull_hard_sets=2,
        squat_hard_sets=6,
        hinge_hard_sets=6,
        push_pull_ratio=5.0,
        squat_hinge_ratio=1.0,
    )
    result = flags.imbalance_flags(b, yaml_config.thresholds)
    assert result == []


def test_recovery_flag_on_hard_set_cap(yaml_config) -> None:
    short = VolumeMetrics(
        hard_sets_by_pattern={"squat": 14, "hinge": 4, "push": 5, "pull": 5},
        total_tonnage_kg=1000,
    )
    result = flags.recovery_flags(
        short_window_metrics=short,
        previous_short_window_metrics=None,
        thresholds=yaml_config.thresholds,
    )
    squat_flag = next(f for f in result if f.get("pattern") == "squat")
    assert squat_flag["kind"] == "recovery_risk"
    assert squat_flag["hard_sets_7d"] == 14


def test_recovery_tonnage_spike_flag(yaml_config) -> None:
    short = VolumeMetrics(total_tonnage_kg=3000)
    prev = VolumeMetrics(total_tonnage_kg=1500)
    result = flags.recovery_flags(
        short_window_metrics=short,
        previous_short_window_metrics=prev,
        thresholds=yaml_config.thresholds,
    )
    spike = next(f for f in result if f.get("subtype") == "tonnage_spike")
    assert spike["ratio"] == 2.0


def test_recovery_no_tonnage_spike_when_below_ratio(yaml_config) -> None:
    short = VolumeMetrics(total_tonnage_kg=1800)
    prev = VolumeMetrics(total_tonnage_kg=1500)
    result = flags.recovery_flags(
        short_window_metrics=short,
        previous_short_window_metrics=prev,
        thresholds=yaml_config.thresholds,
    )
    assert all(f.get("subtype") != "tonnage_spike" for f in result)
