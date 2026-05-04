from __future__ import annotations

from pwrbot.rules.recommendation import recommend_next_workout


def _metrics(
    *,
    hard_7d: dict[str, int] | None = None,
    balance_28d: dict[str, int | float] | None = None,
) -> dict:
    return {
        "last_7d": {"hard_sets_by_pattern": hard_7d or {}},
        "balance_28d": balance_28d or {},
    }


def test_recommendation_prioritizes_unblocked_imbalance(yaml_config) -> None:
    flags = [
        {
            "kind": "imbalance",
            "axis": "push_pull",
            "ratio": 2.0,
            "target": 1.0,
            "push_hard_sets": 12,
            "pull_hard_sets": 6,
        }
    ]
    rec = recommend_next_workout(
        metrics=_metrics(hard_7d={"pull": 6, "push": 10}),
        flags=flags,
        thresholds=yaml_config.thresholds,
    )

    assert rec.focus_pattern == "pull"
    assert "push относительно pull" in rec.rationale[0]


def test_recommendation_skips_imbalance_target_at_weekly_cap(yaml_config) -> None:
    flags = [
        {
            "kind": "imbalance",
            "axis": "squat_hinge",
            "ratio": 2.0,
            "target": 1.0,
            "squat_hard_sets": 12,
            "hinge_hard_sets": 6,
        }
    ]
    rec = recommend_next_workout(
        metrics=_metrics(hard_7d={"hinge": 10, "squat": 8, "push": 4, "pull": 12}),
        flags=flags,
        thresholds=yaml_config.thresholds,
    )

    assert rec.focus_pattern == "push"
    assert "hinge" in rec.caution_patterns


def test_recommendation_uses_lowest_relative_recent_hard_sets(yaml_config) -> None:
    rec = recommend_next_workout(
        metrics=_metrics(hard_7d={"squat": 6, "hinge": 8, "push": 4, "pull": 12}),
        flags=[],
        thresholds=yaml_config.thresholds,
    )

    assert rec.focus_pattern == "push"
    assert "4/16" in rec.rationale[1]


def test_recommendation_falls_back_to_recovery_when_all_patterns_blocked(yaml_config) -> None:
    rec = recommend_next_workout(
        metrics=_metrics(hard_7d={"squat": 12, "hinge": 10, "push": 16, "pull": 18}),
        flags=[],
        thresholds=yaml_config.thresholds,
    )

    assert rec.focus_pattern == "recovery"
    assert set(rec.caution_patterns) == {"squat", "hinge", "push", "pull"}
