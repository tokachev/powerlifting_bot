from __future__ import annotations

from pwrbot.db.repo import ExerciseRow, SetRow, WorkoutRow
from pwrbot.rules import volume


def _set(reps: int, kg: float, rpe: float | None = None, warmup: bool = False, idx: int = 1) -> SetRow:
    return SetRow(
        reps=reps, weight_g=int(kg * 1000), rpe=rpe, is_warmup=warmup, set_index=idx
    )


def _workout(performed_at: int, exercises: list[ExerciseRow]) -> WorkoutRow:
    return WorkoutRow(
        id=1,
        user_id=1,
        performed_at=performed_at,
        logged_at=performed_at,
        source_text="",
        notes=None,
        exercises=exercises,
    )


def _ex(name: str, pattern: str, sets: list[SetRow]) -> ExerciseRow:
    return ExerciseRow(
        position=1, raw_name=name, canonical_name=name, movement_pattern=pattern, sets=sets
    )


def test_tonnage_excludes_warmup(yaml_config, now_ts):
    workouts = [
        _workout(
            now_ts,
            [
                _ex(
                    "squat",
                    "squat",
                    [
                        _set(10, 60, warmup=True),
                        _set(5, 100, rpe=8),
                        _set(5, 100, rpe=8),
                    ],
                )
            ],
        )
    ]
    m = volume.compute(workouts, yaml_config.thresholds)
    assert m.total_working_sets == 2
    assert m.total_tonnage_kg == 5 * 100 + 5 * 100
    assert m.tonnage_by_pattern_kg["squat"] == 1000.0
    assert m.hard_sets_by_pattern["squat"] == 2


def test_hard_sets_by_rpe(yaml_config, now_ts):
    workouts = [
        _workout(
            now_ts,
            [
                _ex(
                    "bench",
                    "push",
                    [_set(5, 80, rpe=6), _set(5, 80, rpe=7), _set(5, 80, rpe=8.5)],
                )
            ],
        )
    ]
    m = volume.compute(workouts, yaml_config.thresholds)
    assert m.total_working_sets == 3
    assert m.hard_sets_by_pattern["push"] == 2  # rpe>=7


def test_hard_sets_intensity_fallback_without_rpe(yaml_config, now_ts):
    history = [
        _workout(
            now_ts - 86400,
            [_ex("squat", "squat", [_set(3, 150, rpe=9)])],
        )
    ]
    current = [
        _workout(
            now_ts,
            [
                _ex(
                    "squat",
                    "squat",
                    [
                        _set(5, 100),   # 100 / 150 = 66% < 75% → not hard
                        _set(5, 120),   # 120 / 150 = 80% ≥ 75% → hard
                    ],
                )
            ],
        )
    ]
    m = volume.compute(current, yaml_config.thresholds, history_for_intensity=history + current)
    assert m.hard_sets_by_pattern["squat"] == 1


def test_no_history_no_rpe_counts_all_as_hard(yaml_config, now_ts):
    workouts = [
        _workout(
            now_ts,
            [_ex("deadlift", "hinge", [_set(5, 100), _set(5, 100)])],
        )
    ]
    m = volume.compute(workouts, yaml_config.thresholds)
    # No history, no RPE → conservative: everything is hard
    assert m.hard_sets_by_pattern["hinge"] == 2
