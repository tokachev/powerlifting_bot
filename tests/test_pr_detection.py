"""Unit tests for PR detection — pure functions, no DB."""

from pwrbot.db.repo import ExerciseRow, SetRow
from pwrbot.metrics.pr import detect_e1rm_prs
from pwrbot.rules.one_rm import estimate_1rm


def _ex(canonical_name, sets, position=0):
    return ExerciseRow(
        position=position,
        raw_name=canonical_name or "raw",
        canonical_name=canonical_name,
        movement_pattern="squat",
        sets=sets,
    )


def _s(reps, weight_g, rpe=None, is_warmup=False, idx=0):
    return SetRow(reps=reps, weight_g=weight_g, rpe=rpe, is_warmup=is_warmup, set_index=idx)


def test_detect_pr_exceeds_previous():
    exercises = [_ex("back_squat", [_s(5, 120_000)])]
    prev = {"back_squat": estimate_1rm(100.0, 5)}  # ~116.7
    prs = detect_e1rm_prs(exercises, prev)
    assert len(prs) == 1
    assert prs[0].canonical_name == "back_squat"
    assert prs[0].pr_type == "e1rm"
    assert prs[0].estimated_1rm_kg == estimate_1rm(120.0, 5)
    assert prs[0].previous_1rm_kg == prev["back_squat"]


def test_no_pr_below_previous():
    exercises = [_ex("back_squat", [_s(5, 80_000)])]
    prev = {"back_squat": estimate_1rm(100.0, 5)}
    prs = detect_e1rm_prs(exercises, prev)
    assert prs == []


def test_no_pr_equal_to_previous():
    e1rm = estimate_1rm(100.0, 5)
    exercises = [_ex("back_squat", [_s(5, 100_000)])]
    prev = {"back_squat": e1rm}
    prs = detect_e1rm_prs(exercises, prev)
    assert prs == []


def test_first_ever_pr():
    exercises = [_ex("bench_press", [_s(3, 80_000)])]
    prs = detect_e1rm_prs(exercises, {})
    assert len(prs) == 1
    assert prs[0].canonical_name == "bench_press"
    assert prs[0].previous_1rm_kg is None


def test_warmup_excluded():
    exercises = [
        _ex("back_squat", [
            _s(5, 200_000, is_warmup=True),  # huge weight but warmup
            _s(5, 80_000, is_warmup=False),
        ]),
    ]
    prev = {"back_squat": estimate_1rm(100.0, 5)}
    prs = detect_e1rm_prs(exercises, prev)
    assert prs == []


def test_high_reps_excluded():
    exercises = [_ex("back_squat", [_s(20, 100_000)])]
    prs = detect_e1rm_prs(exercises, {})
    assert prs == []


def test_zero_weight_excluded():
    exercises = [_ex("pullup", [_s(10, 0)])]
    prs = detect_e1rm_prs(exercises, {})
    assert prs == []


def test_zero_reps_excluded():
    exercises = [_ex("back_squat", [_s(0, 100_000)])]
    prs = detect_e1rm_prs(exercises, {})
    assert prs == []


def test_best_set_wins_within_exercise():
    exercises = [
        _ex("back_squat", [
            _s(5, 100_000, idx=0),
            _s(3, 110_000, idx=1),  # higher e1RM
            _s(8, 80_000, idx=2),
        ]),
    ]
    prs = detect_e1rm_prs(exercises, {})
    assert len(prs) == 1
    assert prs[0].weight_kg == 110.0
    assert prs[0].reps == 3


def test_no_canonical_name_skipped():
    exercises = [_ex(None, [_s(5, 100_000)])]
    prs = detect_e1rm_prs(exercises, {})
    assert prs == []


def test_multiple_exercises_multiple_prs():
    exercises = [
        _ex("back_squat", [_s(5, 100_000)]),
        _ex("bench_press", [_s(5, 70_000)]),
    ]
    prs = detect_e1rm_prs(exercises, {})
    assert len(prs) == 2
    names = {pr.canonical_name for pr in prs}
    assert names == {"back_squat", "bench_press"}
