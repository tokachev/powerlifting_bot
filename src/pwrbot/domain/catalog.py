"""Exercise catalog loader and normalized lookup.

Lookup is case-insensitive and tolerates common punctuation, ё→е, extra whitespace,
and the "подход/подхода/подходов" family of suffixes. Matching is done by a single
normalization function applied to both the catalog aliases and the raw user input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

VALID_MOVEMENT_PATTERNS = frozenset(
    {"squat", "hinge", "push", "pull", "carry", "core", "accessory", "unknown"}
)
VALID_TARGET_GROUPS = frozenset({"squat", "bench", "deadlift"})
VALID_MUSCLE_GROUPS = frozenset({"legs", "chest", "back", "shoulders", "arms", "core"})


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    canonical_name: str
    movement_pattern: str
    aliases: tuple[str, ...]
    target_group: str | None = None
    muscle_group: str | None = None
    is_bilateral_dumbbell: bool = False
    # Ratio of this variant's 1RM to the primary competition lift 1RM.
    # Primary lifts (back_squat, bench_press, deadlift) are 1.0; variants like
    # front_squat are <1.0 so that main-lift max = variant_1RM / coefficient.
    # Required for entries with target_group set; None for non-SBD exercises.
    main_lift_coefficient: float | None = None


_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_MULTISPACE_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Normalize free text for catalog matching.

    Steps: lowercase, ё→е, strip punctuation, collapse whitespace.
    """
    t = text.strip().lower().replace("ё", "е")
    t = _PUNCT_RE.sub(" ", t)
    t = _MULTISPACE_RE.sub(" ", t).strip()
    return t


class Catalog:
    """Loaded exercise catalog. Resolves raw names to canonical + movement_pattern."""

    def __init__(self, entries: list[CatalogEntry]) -> None:
        self._entries = entries
        self._by_alias: dict[str, CatalogEntry] = {}
        self._by_canonical: dict[str, CatalogEntry] = {}
        for e in entries:
            for alias in e.aliases:
                self._by_alias[normalize(alias)] = e
            # canonical key itself is also a valid alias
            self._by_alias[normalize(e.canonical_name.replace("_", " "))] = e
            self._by_canonical[e.canonical_name] = e

    @property
    def canonical_names(self) -> list[str]:
        return [e.canonical_name for e in self._entries]

    @property
    def entries(self) -> list[CatalogEntry]:
        return list(self._entries)

    def by_canonical(self, canonical_name: str) -> CatalogEntry | None:
        return self._by_canonical.get(canonical_name)

    def resolve(self, raw_name: str) -> CatalogEntry | None:
        """Exact-match lookup on normalized text, then longest-prefix fallback.

        The prefix pass handles lines where the exercise name is followed by
        extra words (e.g. "присед со штангой 4x5x100"): we match the longest
        alias that is a prefix of the normalized input.
        """
        norm = normalize(raw_name)
        if not norm:
            return None
        if norm in self._by_alias:
            return self._by_alias[norm]

        # longest-prefix fallback on tokens
        tokens = norm.split(" ")
        for upper in range(len(tokens), 0, -1):
            candidate = " ".join(tokens[:upper])
            if candidate in self._by_alias:
                return self._by_alias[candidate]
        return None


def load_catalog(path: Path) -> Catalog:
    with path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}
    entries: list[CatalogEntry] = []
    for canonical_name, body in raw.items():
        if not isinstance(body, dict):
            continue
        aliases_raw = body.get("aliases", [])
        if not isinstance(aliases_raw, list):
            aliases_raw = []

        movement_pattern = str(body.get("movement_pattern", "unknown"))
        if movement_pattern not in VALID_MOVEMENT_PATTERNS:
            raise ValueError(
                f"{canonical_name}: invalid movement_pattern {movement_pattern!r}; "
                f"allowed: {sorted(VALID_MOVEMENT_PATTERNS)}"
            )

        target_group_raw = body.get("target_group")
        target_group = str(target_group_raw) if target_group_raw is not None else None
        if target_group is not None and target_group not in VALID_TARGET_GROUPS:
            raise ValueError(
                f"{canonical_name}: invalid target_group {target_group!r}; "
                f"allowed: {sorted(VALID_TARGET_GROUPS)} or null"
            )

        muscle_group_raw = body.get("muscle_group")
        muscle_group = str(muscle_group_raw) if muscle_group_raw is not None else None
        if muscle_group is not None and muscle_group not in VALID_MUSCLE_GROUPS:
            raise ValueError(
                f"{canonical_name}: invalid muscle_group {muscle_group!r}; "
                f"allowed: {sorted(VALID_MUSCLE_GROUPS)} or null"
            )

        is_bilateral_dumbbell = bool(body.get("is_bilateral_dumbbell", False))

        coef_raw = body.get("main_lift_coefficient")
        main_lift_coefficient: float | None
        if coef_raw is None:
            main_lift_coefficient = None
        else:
            try:
                main_lift_coefficient = float(coef_raw)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"{canonical_name}: main_lift_coefficient must be a number, "
                    f"got {coef_raw!r}"
                ) from e
            if not 0.0 < main_lift_coefficient <= 2.0:
                raise ValueError(
                    f"{canonical_name}: main_lift_coefficient must be in (0, 2], "
                    f"got {main_lift_coefficient}"
                )
        if target_group is not None and main_lift_coefficient is None:
            raise ValueError(
                f"{canonical_name}: main_lift_coefficient is required when "
                f"target_group is set"
            )
        if target_group is None and main_lift_coefficient is not None:
            raise ValueError(
                f"{canonical_name}: main_lift_coefficient requires target_group "
                f"to be set"
            )

        entries.append(
            CatalogEntry(
                canonical_name=canonical_name,
                movement_pattern=movement_pattern,
                aliases=tuple(str(a) for a in aliases_raw),
                target_group=target_group,
                muscle_group=muscle_group,
                is_bilateral_dumbbell=is_bilateral_dumbbell,
                main_lift_coefficient=main_lift_coefficient,
            )
        )
    return Catalog(entries)
