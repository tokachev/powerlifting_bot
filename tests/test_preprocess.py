"""Unit tests for parsing.preprocess — date extraction + line grouping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pwrbot.parsing.preprocess import (
    _split_name_and_tail,
    extract_header_date,
    group_into_blocks,
    parse_workout_date,
)

NOW = datetime(2026, 4, 11, 12, 0, 0, tzinfo=UTC)


# ── parse_workout_date ─────────────────────────────────────────────────────

def test_parse_today_yesterday():
    today = NOW.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    assert parse_workout_date("сегодня", NOW) == today
    assert parse_workout_date("вчера", NOW) == today.replace(day=10)
    assert parse_workout_date("позавчера", NOW) == today.replace(day=9)


def test_parse_day_month_russian():
    d = parse_workout_date("8 марта", NOW)
    assert d == datetime(2026, 3, 8, tzinfo=UTC)


def test_parse_month_day_russian():
    """`Март 8` (month-first) is also accepted as a date header."""
    d = parse_workout_date("Март 8", NOW)
    assert d == datetime(2026, 3, 8, tzinfo=UTC)
    # with explicit year
    d = parse_workout_date("апреля 15 2025", NOW)
    assert d == datetime(2025, 4, 15, tzinfo=UTC)
    # month-day header in extract_header_date strips cleanly
    body, d = extract_header_date("Март 8\nжим 4x5x100", NOW)
    assert body == "жим 4x5x100"
    assert d == datetime(2026, 3, 8, tzinfo=UTC)


def test_parse_day_month_all_months():
    # Each canonical month word resolves. Use an explicit year so the test
    # isn't sensitive to NOW-dependent rollback thresholds.
    for word, expected_month in [
        ("января", 1), ("февраля", 2), ("марта", 3), ("апреля", 4),
        ("мая", 5), ("июня", 6), ("июля", 7), ("августа", 8),
        ("сентября", 9), ("октября", 10), ("ноября", 11), ("декабря", 12),
    ]:
        d = parse_workout_date(f"1 {word} 2025", NOW)
        assert d is not None, word
        assert d.year == 2025, word
        assert d.month == expected_month, word


def test_parse_with_yo_folding():
    # ё → е is handled inside parse
    d = parse_workout_date("вчёра", NOW)
    assert d is not None


def test_parse_numeric_dmy():
    assert parse_workout_date("12.03", NOW) == datetime(2026, 3, 12, tzinfo=UTC)
    assert parse_workout_date("12.03.2025", NOW) == datetime(2025, 3, 12, tzinfo=UTC)
    assert parse_workout_date("12.03.25", NOW) == datetime(2025, 3, 12, tzinfo=UTC)


def test_parse_iso():
    assert parse_workout_date("2026-03-12", NOW) == datetime(2026, 3, 12, tzinfo=UTC)


def test_rollback_to_past_year_when_future():
    """Date in current year is in the future → roll back to previous year.

    NOW = 2026-04-11. `12 декабря` with implicit year → 2026-12-12 (future) →
    roll back to 2025-12-12.
    """
    d = parse_workout_date("12 декабря", NOW)
    assert d == datetime(2025, 12, 12, tzinfo=UTC)


def test_reject_implicit_rollback_beyond_11_months():
    """Implicit year rollback that lands more than 11 months in the past is rejected.

    NOW = 2026-04-11. `1 мая` (implicit) rolls back to 2025-05-01, which is
    345 days before NOW → beyond the 335-day implicit-year limit.
    """
    assert parse_workout_date("1 мая", NOW) is None
    # `30 мая` rolls back to 2025-05-30, 316 days before NOW → accepted.
    d = parse_workout_date("30 мая", NOW)
    assert d == datetime(2025, 5, 30, tzinfo=UTC)


def test_explicit_year_allowed_up_to_5_years():
    """Explicit-year dates use a lax 5-year threshold, no rollback."""
    d = parse_workout_date("2025-03-12", NOW)
    assert d == datetime(2025, 3, 12, tzinfo=UTC)
    # 5+ years old → rejected
    assert parse_workout_date("2020-01-01", NOW) is None


def test_reject_explicit_future_date():
    assert parse_workout_date("2027-01-01", NOW) is None


def test_parse_garbage():
    assert parse_workout_date("какая-то ерунда", NOW) is None
    assert parse_workout_date("", NOW) is None


# ── extract_header_date ────────────────────────────────────────────────────

def test_extract_header_simple():
    body, d = extract_header_date("8 марта\nжим 4x5x100", NOW)
    assert body == "жим 4x5x100"
    assert d == datetime(2026, 3, 8, tzinfo=UTC)


def test_extract_header_multiline_body():
    text = "8 марта\nЖим штанги лежа 20/50/80/110*12\n115/120/125*5"
    body, d = extract_header_date(text, NOW)
    assert body == "Жим штанги лежа 20/50/80/110*12\n115/120/125*5"
    assert d == datetime(2026, 3, 8, tzinfo=UTC)


def test_extract_header_no_date():
    """First line is not a date → body unchanged, d=None."""
    body, d = extract_header_date("жим 4x5x100\nтяга 3x8x80", NOW)
    assert body == "жим 4x5x100\nтяга 3x8x80"
    assert d is None


def test_extract_header_first_line_has_exercise_not_date():
    """First line has letters AND numbers but isn't a pure date → unchanged."""
    body, d = extract_header_date("8 марта жим 4x5x100", NOW)
    assert body == "8 марта жим 4x5x100"
    assert d is None


def test_extract_header_today():
    body, d = extract_header_date("Сегодня\nжим 4x5x100", NOW)
    assert body == "жим 4x5x100"
    expected = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    assert d == expected


def test_extract_header_leading_blank_line():
    """Leading blank lines are skipped when looking for the header."""
    body, d = extract_header_date("\n\n8 марта\nжим 4x5x100", NOW)
    assert body == "жим 4x5x100"
    assert d == datetime(2026, 3, 8, tzinfo=UTC)


def test_extract_header_yesterday():
    body, d = extract_header_date("вчера\nжим 4x5x100", NOW)
    assert body == "жим 4x5x100"
    assert d == NOW.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)


# ── group_into_blocks ──────────────────────────────────────────────────────

def test_group_single_full_line():
    blocks = group_into_blocks("жим 4x5x100")
    assert len(blocks) == 1
    assert blocks[0].raw_name == "жим"
    assert blocks[0].numeric_segments == ["4x5x100"]


def test_group_multiline_continuation():
    """Format A-style: one exercise, second line is a ladder continuation."""
    text = (
        "Жим штанги лежа 20/50/80/110*12\n"
        "115/120/125/130/135/140/145*5"
    )
    blocks = group_into_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].raw_name == "Жим штанги лежа"
    assert blocks[0].numeric_segments == [
        "20/50/80/110*12",
        "115/120/125/130/135/140/145*5",
    ]


def test_group_name_only_line_followed_by_continuations():
    """Format C: exercise name on its own line, then 3 ladder continuations."""
    text = (
        "Становая сумо лямки\n"
        "20/60/100/130*5\n"
        "150/170/190*3\n"
        "210 2*2 220 1 * 2"
    )
    blocks = group_into_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].raw_name == "Становая сумо лямки"
    assert blocks[0].numeric_segments == [
        "20/60/100/130*5",
        "150/170/190*3",
        "210 2*2 220 1 * 2",
    ]


def test_group_blank_line_splits_blocks():
    text = "жим 4x5x100\n\nтяга 3x8x80"
    blocks = group_into_blocks(text)
    assert len(blocks) == 2
    assert blocks[0].raw_name == "жим"
    assert blocks[1].raw_name == "тяга"


def test_group_mixed_full_and_continuation():
    """Format B: first exercise has a continuation line, second is full."""
    text = (
        "Жим штанги лежа 20/50/80/110*12\n"
        "115/120/125*5\n"
        "Жим с резиной 100 3*8"
    )
    blocks = group_into_blocks(text)
    assert len(blocks) == 2
    assert blocks[0].raw_name == "Жим штанги лежа"
    assert blocks[0].numeric_segments == ["20/50/80/110*12", "115/120/125*5"]
    assert blocks[1].raw_name == "Жим с резиной"
    assert blocks[1].numeric_segments == ["100 3*8"]


def test_group_orphan_continuation_has_empty_name():
    """A continuation with no preceding block → emitted with empty raw_name."""
    blocks = group_into_blocks("20/40/60*10")
    assert len(blocks) == 1
    assert blocks[0].raw_name == ""
    assert blocks[0].numeric_segments == ["20/40/60*10"]


def test_group_name_with_trailing_punct_stripped():
    blocks = group_into_blocks("жим лёжа: 3x8x80")
    assert len(blocks) == 1
    assert blocks[0].raw_name == "жим лёжа"


# ── technique modifier stripping ─────────────────────────────────────────

@pytest.mark.parametrize("line,expected_name", [
    ("Жим штанги лежа пауза 2с 20/50/80/110*5", "Жим штанги лежа"),
    ("Жим штанги лежа пауза 2 с 20/50/80/110*5", "Жим штанги лежа"),
    ("Жим штанги лежа 2с пауза 20/50/80/110*5", "Жим штанги лежа"),
    ("Жим штанги лежа с паузой 2с 20/50/80/110*5", "Жим штанги лежа"),
    ("Жим штанги лежа пауза 3 сек 20/50/80/110*5", "Жим штанги лежа"),
    # descriptive words between pause keyword and duration
    ("Присед оверхед с паузой внизу 1сек 20/50/80/110*5", "Присед оверхед"),
    ("Жим штанги лежа с паузой на груди 2с 20/50/80/110*5", "Жим штанги лежа"),
    ("Жим штанги лежа с паузой в нижней точке 2сек 20/50/80/110*5", "Жим штанги лежа"),
])
def test_split_name_strips_technique_modifier(line, expected_name):
    name, tail = _split_name_and_tail(line)
    assert name == expected_name
    assert "20/50/80/110*5" in tail


# ── annotation lines ("далее без пауз") ─────────────────────────────────

def test_annotation_dalее_transparent():
    """'Далее без пауз' must not break the block — continuation lines stay
    attached to the previous exercise."""
    blocks = group_into_blocks(
        "Жим штанги лежа пауза 2с 20/50*10 70/90/110/120*4\n"
        "Далее без пауз\n"
        "130 2*2 140/145/150/155*3"
    )
    assert len(blocks) == 1
    assert "жим" in blocks[0].raw_name.lower()
    assert len(blocks[0].numeric_segments) == 2
