"""Normalize a parsed workout: resolve canonical names, apply warmup-by-weight rule,
convert kg → grams for persistence."""

from __future__ import annotations

from pwrbot.config import YamlConfig
from pwrbot.db.repo import ExerciseRow, SetRow
from pwrbot.domain.catalog import Catalog
from pwrbot.domain.models import ExercisePayload, SetPayload, WorkoutPayload


def kg_to_g(kg: float) -> int:
    return round(kg * 1000)


def apply_warmup_by_weight(
    sets: list[SetPayload], fraction: float
) -> list[SetPayload]:
    """Single source of truth for warmup detection by weight.

    For sets with weight > 0: OVERWRITE ``is_warmup`` to ``weight < max * fraction``,
    where ``max`` is the heaviest weight in the exercise. Any incoming
    ``is_warmup=True`` from the LLM/regex parsers is ignored — LLM is unreliable for
    ascending ladders (it tends to paint the entire progression as "warmup").

    For sets with weight == 0: preserve the original ``is_warmup`` flag, so that
    the regex "разминка" marker keeps working for bodyweight/machine sets where
    there is no weight to compare against.

    Pure function, returns a new list.
    """
    with_weight = [s for s in sets if s.weight_kg > 0]
    if not with_weight:
        return list(sets)
    max_weight = max(s.weight_kg for s in with_weight)
    threshold = max_weight * fraction
    out: list[SetPayload] = []
    for s in sets:
        if s.weight_kg <= 0:
            # No weight → can't reason by this rule, keep whatever came in.
            out.append(s)
            continue
        out.append(s.model_copy(update={"is_warmup": s.weight_kg < threshold}))
    return out


def resolve_exercise(
    ex: ExercisePayload, catalog: Catalog
) -> ExercisePayload:
    """Try to fill canonical_name from the catalog. LLM fallback happens elsewhere."""
    if ex.canonical_name:
        return ex
    entry = catalog.resolve(ex.raw_name)
    if entry is None:
        return ex
    return ex.model_copy(update={"canonical_name": entry.canonical_name})


def movement_pattern_for(canonical_name: str | None, catalog: Catalog) -> str | None:
    if canonical_name is None:
        return None
    for e in catalog._entries:
        if e.canonical_name == canonical_name:
            return e.movement_pattern
    return None


def normalize_workout(
    payload: WorkoutPayload, catalog: Catalog, cfg: YamlConfig
) -> WorkoutPayload:
    """Apply catalog lookup + warmup-by-weight rule. Returns a new payload."""
    new_exercises: list[ExercisePayload] = []
    frac = cfg.thresholds.warmup.max_fraction_of_working_weight
    for ex in payload.exercises:
        ex = resolve_exercise(ex, catalog)
        ex = ex.model_copy(update={"sets": apply_warmup_by_weight(ex.sets, frac)})
        new_exercises.append(ex)
    return payload.model_copy(update={"exercises": new_exercises})


def to_repo_exercises(
    payload: WorkoutPayload, catalog: Catalog
) -> list[ExerciseRow]:
    """Convert a normalized payload to DB DTOs (grams, 1-based positions)."""
    rows: list[ExerciseRow] = []
    for pos, ex in enumerate(payload.exercises, start=1):
        rows.append(
            ExerciseRow(
                position=pos,
                raw_name=ex.raw_name,
                canonical_name=ex.canonical_name,
                movement_pattern=movement_pattern_for(ex.canonical_name, catalog),
                sets=[
                    SetRow(
                        reps=s.reps,
                        weight_g=kg_to_g(s.weight_kg),
                        rpe=s.rpe,
                        is_warmup=s.is_warmup,
                        set_index=i,
                    )
                    for i, s in enumerate(ex.sets, start=1)
                ],
            )
        )
    return rows
