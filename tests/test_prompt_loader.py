"""Prompt loader must handle templates with literal JSON examples.

Regression test for the bug where canonicalize_exercise.md contained
`{"canonical_name": "bench_press"}` as an example and str.format_map blew up
with "Invalid format specifier".
"""

from __future__ import annotations

from pathlib import Path

from pwrbot.llm.prompt_loader import PromptLoader

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_render_replaces_identifier_placeholders(tmp_path: Path) -> None:
    p = tmp_path / "sample.md"
    p.write_text("Hello, {name}! Age: {age}.", encoding="utf-8")
    loader = PromptLoader(tmp_path)
    out = loader.render("sample", name="Alice", age="30")
    assert out == "Hello, Alice! Age: 30."


def test_render_leaves_literal_json_alone(tmp_path: Path) -> None:
    """Curly braces inside a JSON example must NOT be treated as placeholders."""
    p = tmp_path / "sample.md"
    p.write_text(
        'Пример ответа: {"canonical_name": "bench_press", "suggestions": []}\n'
        'Вход: "{raw_name}"',
        encoding="utf-8",
    )
    loader = PromptLoader(tmp_path)
    out = loader.render("sample", raw_name="приседания")
    assert '{"canonical_name": "bench_press", "suggestions": []}' in out
    assert '"приседания"' in out


def test_render_leaves_unknown_placeholders_intact(tmp_path: Path) -> None:
    p = tmp_path / "sample.md"
    p.write_text("A={a} B={b}", encoding="utf-8")
    loader = PromptLoader(tmp_path)
    out = loader.render("sample", a="1")
    assert out == "A=1 B={b}"


def test_render_all_repo_prompts_load_and_render() -> None:
    """Smoke test against the real prompts/*.md files."""
    loader = PromptLoader(REPO_ROOT / "prompts")
    parse_out = loader.render(
        "parse_workout",
        schema_json='{"type":"object"}',
        now_iso="2026-04-11T12:00:00Z",
        user_text="присед 5x5x100",
    )
    assert "присед 5x5x100" in parse_out
    assert "2026-04-11T12:00:00Z" in parse_out

    canon_out = loader.render(
        "canonicalize_exercise",
        raw_name="шраги",
        catalog_keys="- back_squat\n- bench_press",
    )
    assert '"шраги"' in canon_out
    # Literal JSON examples from the prompt must survive
    assert '"canonical_name": "bench_press"' in canon_out

    explain_out = loader.render(
        "explain_findings",
        metrics_json='{"tonnage":1000}',
        flags_json="[]",
        window_days="7",
    )
    assert '"tonnage":1000' in explain_out
    assert " 7 " in explain_out  # window_days substituted
