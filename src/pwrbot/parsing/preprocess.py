"""Pre-parse text transformations: header date extraction + line grouping.

Runs BEFORE regex_parser so regex stays stateless and per-line. Two responsibilities:

1. `extract_header_date(text, now)` — if the first line of the message is
   itself a parseable date (`сегодня`, `вчера`, `8 марта`, `12.03`,
   `2026-03-08`), strip it from the body and return `(body, date)`. Otherwise
   returns `(text, None)`. Rollback / threshold rules for implicit vs explicit
   years are enforced by `parse_workout_date`.

2. `group_into_blocks(body)` — classify each line as NAME_ONLY / CONTINUATION /
   FULL / BLANK and stitch continuation lines to the block they belong to.
   Produces a list of `LogicalBlock(raw_name, numeric_segments)` that the
   regex parser consumes through `parse_blocks`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

# ── date parsing ────────────────────────────────────────────────────────────

_MONTHS_RU: dict[str, int] = {
    "январь": 1, "января": 1, "янв": 1,
    "февраль": 2, "февраля": 2, "фев": 2, "февр": 2,
    "март": 3, "марта": 3, "мар": 3,
    "апрель": 4, "апреля": 4, "апр": 4,
    "май": 5, "мая": 5,
    "июнь": 6, "июня": 6, "июн": 6,
    "июль": 7, "июля": 7, "июл": 7,
    "август": 8, "августа": 8, "авг": 8,
    "сентябрь": 9, "сентября": 9, "сен": 9, "сент": 9,
    "октябрь": 10, "октября": 10, "окт": 10,
    "ноябрь": 11, "ноября": 11, "ноя": 11, "нояб": 11,
    "декабрь": 12, "декабря": 12, "дек": 12,
}

_RE_DAY_MONTH = re.compile(
    r"^\s*(?P<day>\d{1,2})\s+(?P<month>[а-я]+)(?:\s+(?P<year>\d{4}))?\s*$",
    re.IGNORECASE,
)
_RE_MONTH_DAY = re.compile(
    r"^\s*(?P<month>[а-я]+)\s+(?P<day>\d{1,2})(?:\s+(?P<year>\d{4}))?\s*$",
    re.IGNORECASE,
)
_RE_NUMERIC_DMY = re.compile(
    r"^\s*(?P<day>\d{1,2})\.(?P<month>\d{1,2})(?:\.(?P<year>\d{2,4}))?\s*$",
)
_RE_ISO = re.compile(r"^\s*(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\s*$")

_MAX_PAST_DAYS_IMPLICIT = 335  # ~11 months: reject if year was not specified
_MAX_PAST_DAYS_EXPLICIT = 365 * 5  # up to 5 years back if user explicitly wrote the year


def _yo_fold(s: str) -> str:
    return s.replace("ё", "е").replace("Ё", "Е")


def _to_utc_midnight(year: int, month: int, day: int) -> datetime | None:
    try:
        return datetime(year, month, day, 0, 0, 0, tzinfo=UTC)
    except ValueError:
        return None


def parse_workout_date(raw: str, now: datetime) -> datetime | None:
    """Parse a free-form date string into a UTC-midnight datetime.

    Supported forms (case-insensitive, `ё→е` folded):
      - `сегодня` / `today` → today's date
      - `вчера` / `yesterday` → now - 1 day
      - `N <ru month>` → current year; if result > now, rolls back one year
      - `N <ru month> YYYY`
      - `DD.MM` / `DD.MM.YY` / `DD.MM.YYYY`
      - `YYYY-MM-DD`

    Rules:
      - Implicit year (`N марта`, `12.03`): roll back one year if the current
        year's date is in the future. Max 11 months in the past.
      - Explicit year (`12.03.2025`, `2025-03-12`, `1 мая 2025`): no rollback,
        no future dates, up to 5 years in the past.
    """
    if not raw:
        return None
    text = _yo_fold(raw).strip().lower()
    if not text:
        return None

    today = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    parsed: datetime | None = None
    year_implicit = False

    if text in ("сегодня", "today"):
        parsed = today
    elif text in ("вчера", "yesterday"):
        parsed = today - timedelta(days=1)
    elif text in ("позавчера",):
        parsed = today - timedelta(days=2)
    else:
        m = _RE_ISO.match(text)
        if m:
            parsed = _to_utc_midnight(int(m.group("y")), int(m.group("m")), int(m.group("d")))
        if parsed is None:
            m = _RE_NUMERIC_DMY.match(text)
            if m:
                day = int(m.group("day"))
                month = int(m.group("month"))
                yraw = m.group("year")
                if yraw is None:
                    year = now.year
                    year_implicit = True
                else:
                    y = int(yraw)
                    year = 2000 + y if y < 100 else y
                parsed = _to_utc_midnight(year, month, day)
        if parsed is None:
            m = _RE_DAY_MONTH.match(text) or _RE_MONTH_DAY.match(text)
            if m:
                day = int(m.group("day"))
                mon_word = m.group("month")
                month = _MONTHS_RU.get(mon_word)
                if month is not None:
                    yraw = m.group("year")
                    if yraw:
                        year = int(yraw)
                    else:
                        year = now.year
                        year_implicit = True
                    parsed = _to_utc_midnight(year, month, day)

    if parsed is None:
        return None

    # Implicit-year rollback: `12 марта` in Feb means last year, not next year.
    if year_implicit and parsed > today:
        rolled = _to_utc_midnight(parsed.year - 1, parsed.month, parsed.day)
        if rolled is not None:
            parsed = rolled

    # Reject future dates outright (explicit-year or failed rollback).
    if parsed > today:
        return None

    limit = _MAX_PAST_DAYS_IMPLICIT if year_implicit else _MAX_PAST_DAYS_EXPLICIT
    if (today - parsed).days > limit:
        return None

    return parsed


def extract_header_date(text: str, now: datetime) -> tuple[str, datetime | None]:
    """If the first non-blank line is a parseable date, strip it and return the
    date + remaining body. Otherwise return (text, None) unchanged.

    A "date line" is any line that matches `parse_workout_date` as a WHOLE
    (the underlying regexes are `^...$` anchored, so `8 марта` is a date but
    `8 марта жим 4x5x100` is not — the latter stays in the body untouched).
    """
    if not text:
        return text, None
    lines = text.splitlines()
    # find the first non-blank line — that's the header candidate
    header_idx = None
    for i, ln in enumerate(lines):
        if ln.strip():
            header_idx = i
            break
    if header_idx is None:
        return text, None

    parsed_date = parse_workout_date(lines[header_idx], now)
    if parsed_date is None:
        return text, None

    # Drop the header line (and any leading blank lines before it), keep the rest.
    remaining = "\n".join(lines[header_idx + 1 :]).lstrip("\n")
    return remaining, parsed_date


# ── line grouping ───────────────────────────────────────────────────────────

_RE_HAS_LETTER = re.compile(r"[A-Za-zА-Яа-яЁё]")
_RE_HAS_DIGIT = re.compile(r"\d")
# A line is a "continuation" if its first non-space char is a digit or a slash
# (e.g. `20/40/60*8` or `/60*8`). We also allow a leading `+` / `-` numeric
# marker (uncommon but harmless).
_RE_STARTS_WITH_NUMERIC = re.compile(r"^\s*[\d/+\-]")

# Technique modifiers like "пауза 2с", "с паузой 2 сек", "2с пауза".
# Stripped before the name/tail split so the digit inside the modifier
# doesn't trick the parser into treating it as a set/weight number.
_RE_TECHNIQUE_MOD = re.compile(
    r"(?:с\s+)?пауз\w*(?:\s+[а-яёА-ЯЁa-zA-Z]+){0,4}\s+\d+\s*с(?:ек\w*)?\b"
    r"|\d+(?:с(?:ек\w*)?|\s+сек\w*)\b(?:\s+[а-яёА-ЯЁa-zA-Z]+){0,4}\s+пауз\w*",
    re.IGNORECASE,
)

# Inline annotations like "Далее без пауз", "Далее с лямками" — not exercise names.
# Skipped transparently so the following continuation lines stay attached to the
# previous exercise block.
_RE_ANNOTATION = re.compile(r"^\s*далее\b", re.IGNORECASE)

# Words that are numeric connectors, not exercise names. A line starting with
# a digit and containing ONLY these as letter-words is still a CONTINUATION.
_NUMERIC_CONNECTORS = frozenset({"на", "по", "кг", "kg", "х", "x"})


@dataclass(slots=True)
class LogicalBlock:
    """A single exercise block assembled from one or more raw text lines.

    `raw_name` is the exercise name exactly as the user wrote it (with
    modifiers / trailing punctuation). `numeric_segments` is a list of
    strings, each representing one raw line of numeric data (sets / ladders).
    For a single-line `FULL` exercise, `numeric_segments` has one element
    containing the portion after the name.
    """

    raw_name: str
    numeric_segments: list[str] = field(default_factory=list)


def _classify(line: str) -> str:
    """Return one of: BLANK, CONTINUATION, NAME_ONLY, FULL, ANNOTATION."""
    if not line.strip():
        return "BLANK"
    if _RE_ANNOTATION.match(line):
        return "ANNOTATION"
    has_letter = bool(_RE_HAS_LETTER.search(line))
    has_digit = bool(_RE_HAS_DIGIT.search(line))
    starts_numeric = bool(_RE_STARTS_WITH_NUMERIC.match(line))
    # "14 на 16", "4 по 15 кг" — connector words don't make it an exercise name
    if has_letter and starts_numeric:
        words = {w.lower() for w in re.findall(r"[A-Za-zА-Яа-яЁё]+", line)}
        if words <= _NUMERIC_CONNECTORS:
            has_letter = False
    if starts_numeric and not has_letter:
        return "CONTINUATION"
    if has_letter and not has_digit:
        return "NAME_ONLY"
    if has_letter and has_digit:
        return "FULL"
    return "BLANK"


def _strip_technique_mods(line: str) -> str:
    """Remove technique modifier annotations (pause duration, etc.) so their
    digits don't interfere with the name/tail split."""
    return _RE_TECHNIQUE_MOD.sub(" ", line)


def _split_name_and_tail(line: str) -> tuple[str, str]:
    """For a FULL line, extract the exercise-name prefix (everything before the
    first digit) and the numeric tail. Matches regex_parser._extract_name
    semantics, but duplicated here to avoid coupling."""
    cleaned = _strip_technique_mods(line)
    m = _RE_HAS_DIGIT.search(cleaned)
    if not m:
        return cleaned.strip(), ""
    name = cleaned[: m.start()].strip()
    name = re.sub(
        r"\b(подход\w*|сет\w*|set\w*|reps?|повтор\w*|по)\b\s*$",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()
    name = name.rstrip(":-—,. ").strip()
    tail = cleaned[m.start():].strip()
    return name, tail


def group_into_blocks(body: str) -> list[LogicalBlock]:
    """Walk `body` line by line and stitch continuation lines onto their block.

    Rules:
      - `NAME_ONLY` opens a new block with no numeric segments yet.
      - `FULL` opens a new block and seeds `numeric_segments` with its numeric tail.
      - `CONTINUATION` appends its content to the current block's segments.
        If there is no current block, the line is emitted as a raw block with
        empty `raw_name` (parser will reject it, triggering LLM fallback).
      - `BLANK` closes the current block. The next non-blank line starts a new one.
    """
    blocks: list[LogicalBlock] = []
    current: LogicalBlock | None = None
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        kind = _classify(line)

        if kind == "ANNOTATION":
            continue  # transparent — doesn't break the current block

        if kind == "BLANK":
            if current is not None:
                if current.raw_name or current.numeric_segments:
                    blocks.append(current)
                current = None
            continue

        if kind == "CONTINUATION":
            if current is None:
                # Orphan continuation with no preceding name — emit as unparseable
                # block so the caller can decide (usually: regex fails → LLM).
                current = LogicalBlock(raw_name="")
            current.numeric_segments.append(line.strip())
            continue

        if kind == "NAME_ONLY":
            # close previous block and start a new name-only block
            if current is not None and (current.raw_name or current.numeric_segments):
                blocks.append(current)
            current = LogicalBlock(raw_name=line.strip())
            continue

        if kind == "FULL":
            if current is not None and (current.raw_name or current.numeric_segments):
                blocks.append(current)
            name, tail = _split_name_and_tail(line)
            current = LogicalBlock(raw_name=name)
            if tail:
                current.numeric_segments.append(tail)
            continue

    if current is not None and (current.raw_name or current.numeric_segments):
        blocks.append(current)

    return blocks
