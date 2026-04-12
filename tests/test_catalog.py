from __future__ import annotations

from pathlib import Path

import pytest

from pwrbot.domain.catalog import (
    VALID_MUSCLE_GROUPS,
    VALID_TARGET_GROUPS,
    load_catalog,
    normalize,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = REPO_ROOT / "config" / "exercises.yaml"


def test_normalize_removes_punctuation_and_yo() -> None:
    assert normalize("Жим лёжа!") == "жим лежа"
    assert normalize("  Присед,  со  штангой ") == "присед со штангой"


def test_catalog_exact_alias_hits() -> None:
    cat = load_catalog(CATALOG_PATH)
    e = cat.resolve("присед")
    assert e is not None
    assert e.canonical_name == "back_squat"
    assert e.movement_pattern == "squat"


def test_catalog_yo_insensitive() -> None:
    cat = load_catalog(CATALOG_PATH)
    e = cat.resolve("жим лёжа")
    assert e is not None
    assert e.canonical_name == "bench_press"


def test_catalog_prefix_fallback() -> None:
    """Name followed by stray tokens should still resolve via longest-prefix match."""
    cat = load_catalog(CATALOG_PATH)
    e = cat.resolve("присед со штангой медленно")
    assert e is not None
    assert e.canonical_name == "back_squat"


def test_catalog_miss_returns_none() -> None:
    cat = load_catalog(CATALOG_PATH)
    assert cat.resolve("абракадабра") is None


def test_canonical_name_resolves_by_snake_case() -> None:
    cat = load_catalog(CATALOG_PATH)
    e = cat.resolve("bench press")
    assert e is not None
    assert e.canonical_name == "bench_press"


def test_deadlift_variants() -> None:
    cat = load_catalog(CATALOG_PATH)
    assert cat.resolve("становая").canonical_name == "deadlift"
    assert cat.resolve("румынка").canonical_name == "romanian_deadlift"
    assert cat.resolve("сумо").canonical_name == "sumo_deadlift"


def test_new_exercises_resolve() -> None:
    cat = load_catalog(CATALOG_PATH)
    assert cat.resolve("присед оверхед").canonical_name == "overhead_squat"
    assert cat.resolve("overhead squat").canonical_name == "overhead_squat"
    assert cat.resolve("пуловер").canonical_name == "pullover"
    assert cat.resolve("пуловер на блоке").canonical_name == "pullover"
    assert cat.resolve("молитва").canonical_name == "cable_crunch"
    assert cat.resolve("молитва на блоке").canonical_name == "cable_crunch"
    assert cat.resolve("молитва на пресс на блоке").canonical_name == "cable_crunch"


def test_new_aliases_resolve() -> None:
    cat = load_catalog(CATALOG_PATH)
    # махи на дельты → lateral_raise
    assert cat.resolve("махи на дельты").canonical_name == "lateral_raise"
    # бицепс с гантелями → dumbbell_bicep_curl (split from bicep_curl)
    assert cat.resolve("бицепс с гантелями").canonical_name == "dumbbell_bicep_curl"
    # французский с гантелями → tricep_extension
    assert cat.resolve("французский с гантелями").canonical_name == "tricep_extension"
    # жим с резиной → bench_press (tech debt: merged, not a separate canonical)
    assert cat.resolve("жим с резиной").canonical_name == "bench_press"
    assert cat.resolve("жим с резинкой").canonical_name == "bench_press"
    # horizontal row typo
    assert cat.resolve("горизонтальня тяга").canonical_name == "seated_row"


def test_goleni_collision() -> None:
    """The single-token `голени` is an alias of calf_raise, while
    `разгибания голени` / `сгибания голени` must resolve to leg_extension /
    leg_curl — longest-prefix match on tokens guarantees this.
    """
    cat = load_catalog(CATALOG_PATH)
    assert cat.resolve("голени").canonical_name == "calf_raise"
    assert cat.resolve("разгибания голени").canonical_name == "leg_extension"
    assert cat.resolve("сгибания голени").canonical_name == "leg_curl"
    # also verify the `ног` variants still work
    assert cat.resolve("разгибания ног").canonical_name == "leg_extension"
    assert cat.resolve("сгибания ног").canonical_name == "leg_curl"


def test_tricep_out_of_head_alias() -> None:
    cat = load_catalog(CATALOG_PATH)
    assert cat.resolve("трицепс из-за головы").canonical_name == "tricep_extension"
    assert cat.resolve("трицепс из за головы").canonical_name == "tricep_extension"
    assert cat.resolve("трицепс из-за головы на блоке").canonical_name == "tricep_extension"


# --- Dashboard taxonomy (target_group / muscle_group) ---


def test_target_group_sbd_assignments() -> None:
    cat = load_catalog(CATALOG_PATH)
    assert cat.resolve("присед").target_group == "squat"
    assert cat.resolve("фронт присед").target_group == "squat"
    assert cat.resolve("жим лежа").target_group == "bench"
    assert cat.resolve("наклонный жим").target_group == "bench"
    assert cat.resolve("становая").target_group == "deadlift"
    assert cat.resolve("сумо").target_group == "deadlift"
    # non-competition variants must NOT be tagged as SBD target
    assert cat.resolve("румынка").target_group is None
    assert cat.resolve("overhead squat").target_group is None
    assert cat.resolve("жим стоя").target_group is None
    assert cat.resolve("жим гантелей лежа").target_group is None


def test_muscle_group_coverage() -> None:
    """Every canonical entry must have a valid muscle_group."""
    cat = load_catalog(CATALOG_PATH)
    missing: list[str] = []
    for name in cat.canonical_names:
        e = cat.resolve(name.replace("_", " "))
        assert e is not None
        if e.muscle_group is None:
            missing.append(name)
        else:
            assert e.muscle_group in VALID_MUSCLE_GROUPS
    assert not missing, f"exercises missing muscle_group: {missing}"


def test_muscle_group_spot_checks() -> None:
    cat = load_catalog(CATALOG_PATH)
    # legs
    assert cat.resolve("присед").muscle_group == "legs"
    assert cat.resolve("румынка").muscle_group == "legs"
    assert cat.resolve("ягодичный мост").muscle_group == "legs"
    # chest
    assert cat.resolve("жим лежа").muscle_group == "chest"
    assert cat.resolve("брусья").muscle_group == "chest"
    # back (deadlift → back by convention)
    assert cat.resolve("становая").muscle_group == "back"
    assert cat.resolve("гиперэкстензия").muscle_group == "back"
    assert cat.resolve("подтягивания").muscle_group == "back"
    assert cat.resolve("тяга штанги").muscle_group == "back"
    # shoulders
    assert cat.resolve("жим стоя").muscle_group == "shoulders"
    assert cat.resolve("face pull").muscle_group == "shoulders"
    assert cat.resolve("махи в стороны").muscle_group == "shoulders"
    # arms
    assert cat.resolve("бицепс").muscle_group == "arms"
    assert cat.resolve("французский жим").muscle_group == "arms"
    # core
    assert cat.resolve("планка").muscle_group == "core"
    assert cat.resolve("прогулка фермера").muscle_group == "core"


def test_invalid_muscle_group_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "back_squat:\n"
        "  movement_pattern: squat\n"
        "  muscle_group: wings\n"
        "  aliases: [присед]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="muscle_group"):
        load_catalog(bad)


def test_invalid_target_group_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "back_squat:\n"
        "  movement_pattern: squat\n"
        "  target_group: press\n"
        "  aliases: [присед]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="target_group"):
        load_catalog(bad)


def test_invalid_movement_pattern_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "back_squat:\n"
        "  movement_pattern: flex\n"
        "  aliases: [присед]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="movement_pattern"):
        load_catalog(bad)


def test_optional_fields_default_to_none(tmp_path: Path) -> None:
    ok = tmp_path / "ok.yaml"
    ok.write_text(
        "my_lift:\n"
        "  movement_pattern: accessory\n"
        "  aliases: [my lift]\n",
        encoding="utf-8",
    )
    cat = load_catalog(ok)
    e = cat.resolve("my lift")
    assert e is not None
    assert e.target_group is None
    assert e.muscle_group is None


def test_valid_sets_contain_expected_members() -> None:
    assert {"squat", "bench", "deadlift"} == set(VALID_TARGET_GROUPS)
    assert {"legs", "chest", "back", "shoulders", "arms", "core"} == set(VALID_MUSCLE_GROUPS)
