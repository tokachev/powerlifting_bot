"""Unit tests for parsing.normalize — warmup-by-weight and bilateral dumbbell doubling.

The key invariant under test: weight-based warmup detection is a SINGLE SOURCE
OF TRUTH for sets with weight > 0 and overrides any incoming is_warmup flag
from the LLM/regex parsers. For weightless sets the original flag is preserved.

Bilateral-dumbbell invariant: exercises marked ``is_bilateral_dumbbell`` in the
catalog have their per-set ``weight_kg`` doubled during normalization so tonnage
reflects the total load (two dumbbells).
"""

from __future__ import annotations

from pwrbot.config import YamlConfig
from pwrbot.domain.catalog import Catalog, CatalogEntry
from pwrbot.domain.models import ExercisePayload, SetPayload, WorkoutPayload
from pwrbot.parsing.normalize import apply_warmup_by_weight, normalize_workout


def _s(weight_kg: float, is_warmup: bool = False, reps: int = 10) -> SetPayload:
    return SetPayload(reps=reps, weight_kg=weight_kg, rpe=None, is_warmup=is_warmup)


def test_ladder_overrides_llm_warmup():
    """Reproduces the original bug: LLM marks the whole 20→120 ladder as warmup
    and we must correct it by looking at weights vs max*fraction."""
    weights = [20, 40, 60, 80, 80, 100, 100, 110, 110, 120, 120]
    sets = [_s(w, is_warmup=True) for w in weights]

    out = apply_warmup_by_weight(sets, fraction=0.6)

    # threshold = 120 * 0.6 = 72 → only 20, 40, 60 remain warmup
    expected_warmup = [w < 72 for w in weights]
    assert [s.is_warmup for s in out] == expected_warmup
    assert sum(s.is_warmup for s in out) == 3
    # Sanity: final working sets of 120 are no longer warmup
    assert out[-1].is_warmup is False
    assert out[-2].is_warmup is False


def test_no_weight_keeps_original_warmup_flag():
    sets = [
        _s(weight_kg=0, is_warmup=True),
        _s(weight_kg=0, is_warmup=False),
    ]
    out = apply_warmup_by_weight(sets, fraction=0.6)
    assert out[0].is_warmup is True
    assert out[1].is_warmup is False


def test_all_weightless_returns_unchanged():
    """If nothing has weight at all, the rule has nothing to reason about and
    should leave the list as-is (structurally a new list, but same flags)."""
    sets = [_s(weight_kg=0, is_warmup=False) for _ in range(4)]
    out = apply_warmup_by_weight(sets, fraction=0.6)
    assert len(out) == 4
    assert all(not s.is_warmup for s in out)


def test_mixed_bodyweight_and_weighted():
    """Bodyweight set mixed in with weighted sets — bodyweight flag is preserved,
    weighted sets are reclassified by the rule."""
    sets = [
        _s(weight_kg=0, is_warmup=False),    # bodyweight → untouched
        _s(weight_kg=30, is_warmup=False),   # 30 < 60 → warmup
        _s(weight_kg=60, is_warmup=False),   # 60 == threshold → NOT warmup (strict <)
        _s(weight_kg=100, is_warmup=False),  # max → working
    ]
    out = apply_warmup_by_weight(sets, fraction=0.6)
    # threshold = 100 * 0.6 = 60
    assert out[0].is_warmup is False
    assert out[1].is_warmup is True
    assert out[2].is_warmup is False
    assert out[3].is_warmup is False


def test_all_weights_above_threshold():
    """Heavy-only session: nothing below 0.6 × max, so nothing is warmup."""
    sets = [_s(w) for w in [90, 100, 100, 95]]
    out = apply_warmup_by_weight(sets, fraction=0.6)
    # max=100, threshold=60, min weight=90 > 60 → nothing is warmup
    assert all(not s.is_warmup for s in out)


def test_false_is_warmup_respected_when_below_threshold():
    """Symmetric check: if the parser said False but weight is below threshold,
    the rule must set it to True."""
    sets = [_s(30, is_warmup=False), _s(100, is_warmup=False)]
    out = apply_warmup_by_weight(sets, fraction=0.6)
    assert out[0].is_warmup is True   # 30 < 60
    assert out[1].is_warmup is False


def test_pure_function_does_not_mutate_input():
    sets = [_s(30, is_warmup=True), _s(100, is_warmup=True)]
    original_flags = [s.is_warmup for s in sets]
    _ = apply_warmup_by_weight(sets, fraction=0.6)
    assert [s.is_warmup for s in sets] == original_flags


def test_format_c_sumo_deadlift_ladder_warmup_distribution():
    """Format C end-to-end warmup rule: 11 sets of sumo deadlift spanning
    20→220 kg. Threshold = 220 * 0.6 = 132. Only 20/60/100/130 are warmup.
    """
    weights = [20, 60, 100, 130, 150, 170, 190, 210, 210, 220, 220]
    sets = [_s(w, is_warmup=False) for w in weights]
    out = apply_warmup_by_weight(sets, fraction=0.6)
    # threshold = 132 → warmup where weight < 132
    expected_warmup_count = 4  # 20, 60, 100, 130
    assert sum(s.is_warmup for s in out) == expected_warmup_count
    assert [s.is_warmup for s in out[:4]] == [True, True, True, True]
    assert all(not s.is_warmup for s in out[4:])


# ── bilateral dumbbell doubling ────────────────────────────────────────────

def _make_catalog(*entries: CatalogEntry) -> Catalog:
    return Catalog(list(entries))


def _dumbbell_entry() -> CatalogEntry:
    return CatalogEntry(
        canonical_name="dumbbell_shoulder_press",
        movement_pattern="push",
        aliases=("жим гантелей стоя",),
        muscle_group="shoulders",
        is_bilateral_dumbbell=True,
    )


def _barbell_entry() -> CatalogEntry:
    return CatalogEntry(
        canonical_name="bench_press",
        movement_pattern="push",
        aliases=("жим лежа",),
        muscle_group="chest",
        is_bilateral_dumbbell=False,
    )


def test_bilateral_dumbbell_doubles_weight(yaml_config: YamlConfig):
    """Dumbbell shoulder press 16 kg per hand → stored as 32 kg total."""
    catalog = _make_catalog(_dumbbell_entry())
    payload = WorkoutPayload(exercises=[
        ExercisePayload(
            raw_name="жим гантелей стоя",
            canonical_name="dumbbell_shoulder_press",
            sets=[
                SetPayload(reps=16, weight_kg=16.0),
                SetPayload(reps=16, weight_kg=16.0),
                SetPayload(reps=16, weight_kg=16.0),
            ],
        ),
    ])

    result = normalize_workout(payload, catalog, yaml_config)

    for s in result.exercises[0].sets:
        assert s.weight_kg == 32.0


def test_barbell_exercise_not_doubled(yaml_config: YamlConfig):
    """Barbell bench press weight must NOT be doubled."""
    catalog = _make_catalog(_barbell_entry())
    payload = WorkoutPayload(exercises=[
        ExercisePayload(
            raw_name="жим лежа",
            canonical_name="bench_press",
            sets=[SetPayload(reps=5, weight_kg=100.0)],
        ),
    ])

    result = normalize_workout(payload, catalog, yaml_config)

    assert result.exercises[0].sets[0].weight_kg == 100.0


def test_bilateral_dumbbell_zero_weight_not_doubled(yaml_config: YamlConfig):
    """Bodyweight sets (weight=0) within a dumbbell exercise stay at 0."""
    catalog = _make_catalog(_dumbbell_entry())
    payload = WorkoutPayload(exercises=[
        ExercisePayload(
            raw_name="жим гантелей стоя",
            canonical_name="dumbbell_shoulder_press",
            sets=[
                SetPayload(reps=10, weight_kg=0.0),
                SetPayload(reps=8, weight_kg=14.0),
            ],
        ),
    ])

    result = normalize_workout(payload, catalog, yaml_config)

    assert result.exercises[0].sets[0].weight_kg == 0.0
    assert result.exercises[0].sets[1].weight_kg == 28.0


def test_bilateral_dumbbell_warmup_uses_doubled_weight(yaml_config: YamlConfig):
    """Warmup threshold is applied AFTER doubling: 8→16 and 16→32.
    max=32, threshold=32*0.6=19.2. Set at 16 kg (doubled) < 19.2 → warmup."""
    catalog = _make_catalog(_dumbbell_entry())
    payload = WorkoutPayload(exercises=[
        ExercisePayload(
            raw_name="жим гантелей стоя",
            canonical_name="dumbbell_shoulder_press",
            sets=[
                SetPayload(reps=10, weight_kg=8.0),   # → 16 kg < 19.2 → warmup
                SetPayload(reps=8, weight_kg=16.0),    # → 32 kg → working
            ],
        ),
    ])

    result = normalize_workout(payload, catalog, yaml_config)

    assert result.exercises[0].sets[0].weight_kg == 16.0
    assert result.exercises[0].sets[0].is_warmup is True
    assert result.exercises[0].sets[1].weight_kg == 32.0
    assert result.exercises[0].sets[1].is_warmup is False


def test_unresolved_exercise_not_doubled(yaml_config: YamlConfig):
    """If canonical_name is None (exercise not resolved), don't double."""
    catalog = _make_catalog(_dumbbell_entry())
    payload = WorkoutPayload(exercises=[
        ExercisePayload(
            raw_name="неизвестное упражнение",
            sets=[SetPayload(reps=10, weight_kg=20.0)],
        ),
    ])

    result = normalize_workout(payload, catalog, yaml_config)

    assert result.exercises[0].sets[0].weight_kg == 20.0
