from __future__ import annotations

from pathlib import Path

from pwrbot.domain.catalog import load_catalog
from pwrbot.llm.prompt_loader import PromptLoader
from pwrbot.parsing.llm_parser import (
    LLMParser,
    _CanonResponse,
    _detect_muscle_group,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = REPO_ROOT / "config" / "exercises.yaml"
PROMPTS_DIR = REPO_ROOT / "prompts"


class _StubClient:
    """Minimal stand-in for OllamaClient.chat_json — returns a canned response
    and records the rendered user prompt for assertions."""

    def __init__(self, response: _CanonResponse) -> None:
        self._response = response
        self.last_user: str | None = None
        self.last_system: str | None = None

    async def chat_json(self, *, system: str, user: str, schema_model):  # type: ignore[no-untyped-def]
        self.last_system = system
        self.last_user = user
        return self._response


def _make_parser(resp: _CanonResponse) -> tuple[LLMParser, _StubClient]:
    cat = load_catalog(CATALOG_PATH)
    client = _StubClient(resp)
    prompts = PromptLoader(PROMPTS_DIR)
    parser = LLMParser(client, prompts, cat)  # type: ignore[arg-type]
    return parser, client


def test_detect_muscle_group_roots() -> None:
    # NB: "Разгибания с канатом из-за головы" has no RU muscle-root token —
    # it's handled by a catalog alias (see test_cable_tricep_aliases), not
    # by the LLM filter. The filter only kicks in when the raw text itself
    # names the muscle.
    assert _detect_muscle_group("трицепс с канатом") == "arms"
    assert _detect_muscle_group("трис на блоке") == "arms"
    assert _detect_muscle_group("махи на дельты") == "shoulders"
    assert _detect_muscle_group("разгибания голени") == "legs"
    assert _detect_muscle_group("упражнение на спину") == "back"
    assert _detect_muscle_group("жим лёжа") is None  # no RU muscle root
    assert _detect_muscle_group("") is None


async def test_canonicalize_filters_wrong_muscle_group_suggestion() -> None:
    """LLM picks cable_row for a triceps input — the muscle-group filter
    must strip it out because cable_row is back, not arms."""
    parser, _ = _make_parser(
        _CanonResponse(canonical_name=None, suggestions=["cable_row"])
    )
    result = await parser.canonicalize("трицепс неизвестное упражнение")
    # cable_row is back → dropped. No arm alternatives from the LLM → fallback
    # kicks in: wrong suggestion is better than nothing.
    assert result.canonical_name is None
    assert result.suggestions == ["cable_row"]


async def test_canonicalize_keeps_correct_muscle_group_pick() -> None:
    parser, _ = _make_parser(
        _CanonResponse(
            canonical_name="tricep_extension",
            suggestions=[],
        )
    )
    result = await parser.canonicalize("трицепс загадочный")
    assert result.canonical_name == "tricep_extension"


async def test_canonicalize_filters_out_wrong_canonical_only() -> None:
    """LLM confidently picks cable_row for triceps input → demote to None
    and keep any correctly-tagged suggestions."""
    parser, _ = _make_parser(
        _CanonResponse(
            canonical_name="cable_row",
            suggestions=["tricep_extension", "tricep_pushdown"],
        )
    )
    result = await parser.canonicalize("трицепс мегаразгиб")
    assert result.canonical_name is None
    assert result.suggestions == ["tricep_extension", "tricep_pushdown"]


async def test_canonicalize_no_muscle_root_means_no_filtering() -> None:
    """If the raw name has no RU muscle root (e.g., pure English), the
    muscle-group filter must not interfere with the LLM output."""
    parser, _ = _make_parser(
        _CanonResponse(
            canonical_name=None,
            suggestions=["cable_row", "seated_row"],
        )
    )
    result = await parser.canonicalize("mysterious pulling thing")
    assert result.suggestions == ["cable_row", "seated_row"]


async def test_canonicalize_fallback_when_filter_empties_everything() -> None:
    """If filtering would wipe both canonical and suggestions, fall back
    to the unfiltered LLM output (wrong is better than nothing)."""
    parser, _ = _make_parser(
        _CanonResponse(
            canonical_name="cable_row",
            suggestions=["seated_row"],
        )
    )
    # Input has an arm root but LLM returned only back exercises. Canonical
    # is demoted (muscle mismatch); suggestions survive via the fallback
    # because filtering would otherwise produce nothing.
    result = await parser.canonicalize("трицепс неведомое упражнение")
    assert result.canonical_name is None
    assert result.suggestions == ["seated_row"]


async def test_canonicalize_prompt_includes_metadata() -> None:
    parser, client = _make_parser(
        _CanonResponse(canonical_name=None, suggestions=[])
    )
    await parser.canonicalize("тяга верхнего блока")
    assert client.last_system is not None
    assert client.last_user is not None
    # catalog list format includes muscle+pattern
    assert "(muscle: back, pattern: pull)" in client.last_user
    assert "(muscle: arms, pattern: accessory)" in client.last_user


async def test_canonicalize_drops_hallucinated_keys() -> None:
    parser, _ = _make_parser(
        _CanonResponse(
            canonical_name="not_in_catalog",
            suggestions=["fake_one", "bench_press"],
        )
    )
    result = await parser.canonicalize("жим lёжа что-то")
    # hallucinated canonical → None; fake_one filtered; bench_press kept
    assert result.canonical_name is None
    assert result.suggestions == ["bench_press"]
