"""Deterministic first-pass parser for Russian training-diary messages.

Handles common formats:
- "3x5x100" / "3х5х100" (latin or cyrillic x, optional cross ×, or asterisk *)
- "5x10 100кг"
- "4 подхода по 8 85кг" / "4 по 8 85" / "4 по 20" (weight optional)
- "20/40/60/80/100*10" (ladder of weights across a shared rep count)
- "100 3*8" / "220 1 * 2" (weight-prefix: weight, then sets*reps)
- "4*15" / "4 * 15" (bodyweight / machine sets with no weight)
- "@rpe 8" / "@8" / "рпе 8"
- "разминка" / "warmup" marker → is_warmup=True for that line

Multi-line continuations (an exercise whose setgroups span several lines) and
multi-setgroup lines (`2 по 12 2 по 10`) are handled via the preprocess module:
it pre-groups the text into LogicalBlocks, and `parse_blocks` walks each block
iteratively from the start, collecting every setgroup until the block is
exhausted.

Returns None if nothing recognizable was parsed, so the LLM fallback kicks in.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from pwrbot.parsing import preprocess

_X = r"[xхХ×*]"
_NUM = r"\d+(?:[.,]\d+)?"
_KG = r"(?:кг|kg)?"
_REP_RANGE = r"(?:-\d+)?"  # optional rep-range tail: "8-12" → capture 8, discard -12

# NOTE on ordering: patterns are tried in the order declared in `_PATTERN_BUILDERS`
# below via `re.Pattern.match(text, pos)` (anchored at a cursor position). Order
# matters — most notably RE_N_STAR_R MUST come last, otherwise `3x8 80` would be
# eaten as a weightless `N*R` match and the trailing weight would be lost.

# "20/40/60/80/100*10" — ladder of weights with a shared rep count
RE_LADDER = re.compile(
    rf"(?P<weights>{_NUM}(?:\s*/\s*{_NUM})+)\s*{_X}\s*(?P<reps>\d+){_REP_RANGE}\s*{_KG}",
    re.IGNORECASE,
)
# "100 3*8" / "220 1 * 2" — weight first, then sets*reps
RE_W_NR = re.compile(
    rf"(?P<weight>{_NUM})\s+(?P<sets>\d+)\s*{_X}\s*(?P<reps>\d+){_REP_RANGE}\s*{_KG}\b",
    re.IGNORECASE,
)
# "3x5x100" / "3х5х100" / "3*5*100" — sets × reps × weight
RE_NRW = re.compile(
    rf"(?P<sets>\d+)\s*{_X}\s*(?P<reps>\d+){_REP_RANGE}\s*{_X}\s*(?P<weight>{_NUM})\s*{_KG}\b",
    re.IGNORECASE,
)
# "5x10 100кг" — sets × reps, then weight after a space
RE_NR_W = re.compile(
    rf"(?P<sets>\d+)\s*{_X}\s*(?P<reps>\d+){_REP_RANGE}\s+(?P<weight>{_NUM})\s*{_KG}\b",
    re.IGNORECASE,
)
# "4 подхода по 8 85кг" / "4 по 8 85" / "4 по 20" (weight optional)
# Negative lookahead BEFORE the optional weight group: if what follows the reps
# looks like the sets-count of a new `N по R` group (i.e. `\s+\d+\s*по`), skip
# the weight capture entirely — otherwise the leading digit of the next group
# gets eaten as weight (data-corruption bug seen with `2 по 12 2 по 10`).
RE_SETS_OF = re.compile(
    rf"(?P<sets>\d+)\s*(?:подход\w*|сет\w*|set\w*)?\s*по\s*(?P<reps>\d+){_REP_RANGE}"
    rf"(?:(?!\s+\d+\s*по)\s+(?P<weight>{_NUM})\s*{_KG})?",
    re.IGNORECASE,
)
# "4*15" / "4 x 15" / "4 * 15" — sets × reps, no weight.
# Negative lookahead on a following number prevents this pattern from eating
# `3x8 80` as (3 sets × 8 reps @ 0kg) and losing the weight — that case belongs
# to RE_NR_W which is tried before this one.
RE_N_STAR_R = re.compile(
    rf"(?P<sets>\d+)\s*{_X}\s*(?P<reps>\d+){_REP_RANGE}\b(?!\s*{_NUM})",
    re.IGNORECASE,
)

# RPE: "@8", "@rpe 8", "rpe 8", "рпе 8"
RE_RPE = re.compile(
    r"(?:@\s*(?:rpe|рпе)?\s*(?P<a>\d+(?:[.,]\d+)?))|(?:\b(?:rpe|рпе)\s*(?P<b>\d+(?:[.,]\d+)?))",
    re.IGNORECASE,
)

RE_WARMUP = re.compile(r"\b(разминк\w*|warmup|warm-up|wu)\b", re.IGNORECASE)
RE_ANY_DIGIT = re.compile(r"\d")


@dataclass(slots=True)
class ParsedSet:
    reps: int
    weight_kg: float
    rpe: float | None
    is_warmup: bool


@dataclass(slots=True)
class ParsedExercise:
    raw_name: str
    sets: list[ParsedSet]


def _to_float(s: str) -> float:
    return float(s.replace(",", "."))


def _parse_rpe(text: str) -> float | None:
    m = RE_RPE.search(text)
    if not m:
        return None
    raw = m.group("a") or m.group("b")
    if raw is None:
        return None
    try:
        v = _to_float(raw)
    except ValueError:
        return None
    if 0 <= v <= 10:
        return v
    return None


def _fix_comma_splits(text: str) -> str:
    """Normalize comma-separated exercises into newline-separated ones.

    A comma or semicolon becomes a newline only if BOTH:
      - the buffer accumulated on the current line already contains at least one
        digit (→ we've already seen a setgroup, so this comma is a delimiter),
      - the next non-space char after the separator is a letter (→ looks like a
        new exercise name, not more digits like `100,5кг`).

    This preserves commas that live inside exercise-name modifiers like
    `Присед, штанга низко` where the comma appears BEFORE any number.
    """
    out_lines: list[str] = []
    for line in text.splitlines():
        buf: list[str] = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch in ",;":
                j = i + 1
                while j < len(line) and line[j] in " \t":
                    j += 1
                next_is_letter = j < len(line) and line[j].isalpha()
                buf_has_digit = any(c.isdigit() for c in buf)
                if next_is_letter and buf_has_digit:
                    out_lines.append("".join(buf).strip())
                    buf = []
                    i = j
                    continue
            buf.append(ch)
            i += 1
        if buf:
            out_lines.append("".join(buf).strip())
    return "\n".join(out_lines)


def _extract_name(line: str) -> str:
    """Everything before the first digit is the raw exercise name.

    Trailing words that are clearly set-descriptors ('подхода', 'по', 'сетов')
    are stripped. 'разминка' is kept — it's a legitimate warmup marker, not a name.
    Technique modifiers like 'пауза 2с' are stripped first so their digits
    don't split the name prematurely.
    """
    from pwrbot.parsing.preprocess import _strip_technique_mods

    cleaned = _strip_technique_mods(line)
    m = RE_ANY_DIGIT.search(cleaned)
    if not m:
        return cleaned.strip()
    name = cleaned[: m.start()].strip()
    name = re.sub(
        r"\b(подход\w*|сет\w*|set\w*|reps?|повтор\w*|по)\b\s*$",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()
    return name.rstrip(":-—,.")


# ── pattern-to-sets builders ────────────────────────────────────────────────

def _build_ladder(
    m: re.Match[str], rpe: float | None, is_warmup: bool
) -> list[ParsedSet] | None:
    r = int(m.group("reps"))
    weights = [_to_float(w.strip()) for w in m.group("weights").split("/")]
    return [
        ParsedSet(reps=r, weight_kg=w, rpe=rpe, is_warmup=is_warmup) for w in weights
    ]


def _build_w_nr(
    m: re.Match[str], rpe: float | None, is_warmup: bool
) -> list[ParsedSet] | None:
    n = int(m.group("sets"))
    r = int(m.group("reps"))
    w = _to_float(m.group("weight"))
    return [ParsedSet(reps=r, weight_kg=w, rpe=rpe, is_warmup=is_warmup) for _ in range(n)]


def _build_nrw(
    m: re.Match[str], rpe: float | None, is_warmup: bool
) -> list[ParsedSet] | None:
    n = int(m.group("sets"))
    r = int(m.group("reps"))
    w = _to_float(m.group("weight"))
    return [ParsedSet(reps=r, weight_kg=w, rpe=rpe, is_warmup=is_warmup) for _ in range(n)]


def _build_nr_w(
    m: re.Match[str], rpe: float | None, is_warmup: bool
) -> list[ParsedSet] | None:
    n = int(m.group("sets"))
    r = int(m.group("reps"))
    w = _to_float(m.group("weight"))
    return [ParsedSet(reps=r, weight_kg=w, rpe=rpe, is_warmup=is_warmup) for _ in range(n)]


def _build_sets_of(
    m: re.Match[str], rpe: float | None, is_warmup: bool
) -> list[ParsedSet] | None:
    n = int(m.group("sets"))
    r = int(m.group("reps"))
    w_raw = m.group("weight")
    w = _to_float(w_raw) if w_raw else 0.0
    return [ParsedSet(reps=r, weight_kg=w, rpe=rpe, is_warmup=is_warmup) for _ in range(n)]


_MAX_BW_SETS = 20  # bodyweight set count cap for N*R fallback pattern


def _build_n_star_r(
    m: re.Match[str], rpe: float | None, is_warmup: bool
) -> list[ParsedSet] | None:
    n = int(m.group("sets"))
    r = int(m.group("reps"))
    if n > _MAX_BW_SETS:
        # Implausible set count — treat N as weight (1 set of R reps @ N kg).
        # Covers single-weight continuations like "220 *2" after a ladder.
        return [ParsedSet(reps=r, weight_kg=float(n), rpe=rpe, is_warmup=is_warmup)]
    return [ParsedSet(reps=r, weight_kg=0.0, rpe=rpe, is_warmup=is_warmup) for _ in range(n)]


# Pattern order is CRITICAL — see module docstring.
_PatternBuilder = Callable[[re.Match[str], float | None, bool], list[ParsedSet] | None]
_PATTERN_BUILDERS: list[tuple[re.Pattern[str], _PatternBuilder]] = [
    (RE_LADDER, _build_ladder),
    (RE_W_NR, _build_w_nr),
    (RE_NRW, _build_nrw),
    (RE_NR_W, _build_nr_w),
    (RE_SETS_OF, _build_sets_of),
    (RE_N_STAR_R, _build_n_star_r),
]


def _skip_seps(text: str, pos: int) -> int:
    while pos < len(text) and text[pos] in " \t,;":
        pos += 1
    return pos


def _match_setgroup_at_start(
    text: str, pos: int, rpe: float | None, is_warmup: bool
) -> tuple[list[ParsedSet], int] | None:
    """Try each pattern anchored at `pos` in order; return the first match.

    Returns `(sets, new_pos)` on success or None if nothing anchored at `pos`
    matched. Patterns are tried in `_PATTERN_BUILDERS` order — RE_N_STAR_R MUST
    be last so `3x8 80` still routes to RE_NR_W (and keeps its weight).
    """
    for pattern, builder in _PATTERN_BUILDERS:
        m = pattern.match(text, pos)
        if m is None:
            continue
        sets = builder(m, rpe, is_warmup)
        if not sets:
            continue
        return sets, m.end()
    return None


def _parse_segment(
    text: str, rpe_global: float | None, warmup_global: bool
) -> list[ParsedSet] | None:
    """Parse one numeric segment (e.g. `20/40/60*10` or `2 по 12 2 по 10`).

    Iteratively consumes setgroups from left to right. Returns None if the
    segment contains non-whitespace content that no pattern matched — the
    caller treats that as a parse failure for the whole block.
    """
    work = RE_WARMUP.sub(" ", text)
    work = RE_RPE.sub(" ", work)

    sets: list[ParsedSet] = []
    pos = _skip_seps(work, 0)
    while pos < len(work):
        hit = _match_setgroup_at_start(work, pos, rpe_global, warmup_global)
        if hit is None:
            break
        new_sets, new_pos = hit
        sets.extend(new_sets)
        pos = _skip_seps(work, new_pos)

    if work[pos:].strip():
        return None
    return sets or None


def parse_blocks(
    blocks: list[preprocess.LogicalBlock],
) -> list[ParsedExercise] | None:
    """Parse a list of LogicalBlocks into ParsedExercises.

    Each block becomes one ParsedExercise whose sets are the concatenation of
    all setgroups parsed from its numeric segments. A block with no resolved
    name OR any unparseable segment marks the entire message as a regex-miss
    (returns None so the LLM fallback kicks in).
    """
    result: list[ParsedExercise] = []
    unparsed = 0
    for block in blocks:
        if not block.raw_name and not block.numeric_segments:
            continue

        combined = " ".join(block.numeric_segments)
        rpe_global = _parse_rpe(combined)
        warmup_global = bool(RE_WARMUP.search(combined))

        all_sets: list[ParsedSet] = []
        block_ok = True
        for seg in block.numeric_segments:
            parsed = _parse_segment(seg, rpe_global, warmup_global)
            if parsed is None:
                block_ok = False
                break
            all_sets.extend(parsed)

        if not block_ok or not all_sets or not block.raw_name:
            unparsed += 1
            continue

        result.append(ParsedExercise(raw_name=block.raw_name, sets=all_sets))

    if not result:
        return None
    if unparsed > 0:
        return None
    return result


def parse(text: str) -> list[ParsedExercise] | None:
    """Backward-compat entry point: text → comma-fix → blocks → ParsedExercises.

    Returns None if nothing could be parsed OR if any block/line failed (so
    the LLM fallback handles the entire message consistently).
    """
    fixed = _fix_comma_splits(text)
    blocks = preprocess.group_into_blocks(fixed)
    return parse_blocks(blocks)
