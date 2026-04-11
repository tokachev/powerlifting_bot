from __future__ import annotations

from pwrbot.parsing import regex_parser
from pwrbot.parsing.regex_parser import parse


def test_nxrxw_latin() -> None:
    result = parse("присед 4x5x100")
    assert result is not None
    assert len(result) == 1
    ex = result[0]
    assert ex.raw_name == "присед"
    assert len(ex.sets) == 4
    assert ex.sets[0].reps == 5
    assert ex.sets[0].weight_kg == 100


def test_nxrxw_cyrillic_x() -> None:
    result = parse("присед 4х5х100")
    assert result is not None
    assert result[0].sets[0].weight_kg == 100


def test_sets_of_reps_ru() -> None:
    result = parse("жим лёжа 5 подходов по 8 80кг")
    assert result is not None
    ex = result[0]
    assert "жим" in ex.raw_name.lower()
    assert len(ex.sets) == 5
    assert ex.sets[0].reps == 8
    assert ex.sets[0].weight_kg == 80


def test_rpe_variants() -> None:
    result = parse("присед 3x5x100 @rpe 8")
    assert result is not None
    assert result[0].sets[0].rpe == 8.0

    result = parse("присед 3x5x100 @8.5")
    assert result is not None
    assert result[0].sets[0].rpe == 8.5

    result = parse("присед 3x5x100 rpe 7")
    assert result is not None
    assert result[0].sets[0].rpe == 7.0


def test_warmup_marker() -> None:
    result = parse("присед 1x10x60 разминка")
    assert result is not None
    assert result[0].sets[0].is_warmup is True


def test_decimal_comma_weight() -> None:
    result = parse("жим 3x5x82,5")
    assert result is not None
    assert result[0].sets[0].weight_kg == 82.5


def test_multi_exercise_newlines() -> None:
    text = "присед 4x5x100\nжим 3x8x80\nстановая 3x3x140"
    result = parse(text)
    assert result is not None
    assert len(result) == 3


def test_multi_exercise_comma() -> None:
    text = "присед 4x5x100, жим 3x8x80, становая 3x3x140"
    result = parse(text)
    assert result is not None
    assert len(result) == 3


def test_unparseable_returns_none() -> None:
    assert parse("просто какой-то текст без чисел и упражнений") is None


def test_partial_failure_returns_none() -> None:
    """Mixed parseable + unparseable lines → None, so LLM handles the whole message."""
    text = "присед 4x5x100\nвчера болела спина, размялся и пошёл"
    assert parse(text) is None


def test_zero_weight_bodyweight() -> None:
    result = parse("подтягивания 4x8 0")
    assert result is not None
    assert result[0].sets[0].weight_kg == 0.0


def test_nr_space_w_with_kg_suffix() -> None:
    result = parse("жим 5x10 100кг")
    assert result is not None
    assert result[0].sets[0].reps == 10
    assert result[0].sets[0].weight_kg == 100
    assert len(result[0].sets) == 5


def test_extract_name_strips_trailing_descriptors() -> None:
    assert regex_parser._extract_name("присед 4x5x100") == "присед"
    assert regex_parser._extract_name("жим лёжа 3x8x80") == "жим лёжа"
    assert regex_parser._extract_name("жим лёжа по 3x8x80").lower() == "жим лёжа"


def test_ladder_slash_star_reps() -> None:
    result = parse("жим 20/40/60/80/100*10")
    assert result is not None
    assert len(result) == 1
    ex = result[0]
    assert len(ex.sets) == 5
    assert [s.weight_kg for s in ex.sets] == [20.0, 40.0, 60.0, 80.0, 100.0]
    assert all(s.reps == 10 for s in ex.sets)
    assert ex.raw_name.strip() == "жим"


def test_ladder_full_bench_progression() -> None:
    """Real-world case from the bug report."""
    result = parse(
        "Жим штанги лежа 20/40/60/80/80/100/100/110/110/120/120*10"
    )
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 11
    assert [s.weight_kg for s in ex.sets] == [
        20.0, 40.0, 60.0, 80.0, 80.0, 100.0, 100.0, 110.0, 110.0, 120.0, 120.0,
    ]
    assert all(s.reps == 10 for s in ex.sets)


def test_ladder_cyrillic_x_reps() -> None:
    result = parse("жим 20/40/60×8")
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 3
    assert [s.weight_kg for s in ex.sets] == [20.0, 40.0, 60.0]
    assert all(s.reps == 8 for s in ex.sets)


def test_ladder_with_kg_suffix() -> None:
    result = parse("жим 50/60/70*5 кг")
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 3
    assert [s.weight_kg for s in ex.sets] == [50.0, 60.0, 70.0]


def test_sets_of_no_weight() -> None:
    result = parse("горизонтальная тяга 4 по 20")
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 4
    assert all(s.reps == 20 for s in ex.sets)
    assert all(s.weight_kg == 0.0 for s in ex.sets)
    assert "горизонтальная тяга" in ex.raw_name.lower()


def test_sets_of_no_weight_accessory() -> None:
    result = parse("сгибания голени 4 по 20")
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 4
    assert all(s.reps == 20 and s.weight_kg == 0.0 for s in ex.sets)


def test_multiline_ladder_and_no_weight() -> None:
    """End-to-end: the exact message from the bug report, minus the pullover."""
    text = (
        "Жим штанги лежа 20/40/60/80/80/100/100/110/110/120/120*10\n"
        "горизонтальная тяга 4 по 20\n"
        "сгибания голени 4 по 20\n"
        "разгибания голени 4 по 15"
    )
    result = parse(text)
    assert result is not None
    assert len(result) == 4
    # bench ladder
    assert len(result[0].sets) == 11
    assert result[0].sets[-1].weight_kg == 120.0
    # three 4-by-R without weight
    for ex in result[1:]:
        assert len(ex.sets) == 4
        assert all(s.weight_kg == 0.0 for s in ex.sets)


# ── Format A: ladder continuation + comma inside exercise-name modifier ─────

def test_format_a_two_ladder_lines_same_exercise() -> None:
    text = (
        "Присед , штанга низко наколенники пояс20/60/90/120*5\n"
        "140/145/150/155*8"
    )
    result = parse(text)
    assert result is not None
    assert len(result) == 1
    ex = result[0]
    assert "присед" in ex.raw_name.lower()
    # 4 ladder weights × 5 + 4 ladder weights × 8 = 8 sets total
    assert len(ex.sets) == 8
    assert [s.weight_kg for s in ex.sets] == [20, 60, 90, 120, 140, 145, 150, 155]
    # first 4 sets are 5 reps, last 4 are 8 reps
    assert [s.reps for s in ex.sets] == [5, 5, 5, 5, 8, 8, 8, 8]


# ── Format B: W N*R weight-prefix + multi-exercise + continuation ───────────

def test_format_b_weight_prefix_and_continuation() -> None:
    text = (
        "Жим штанги лежа 20/50/80/110*12\n"
        "115/120/125/130/135/140/145*5\n"
        "Жим с резиной 100 3*8"
    )
    result = parse(text)
    assert result is not None
    assert len(result) == 2
    bench = result[0]
    assert "жим штанги лежа" in bench.raw_name.lower()
    assert len(bench.sets) == 4 + 7  # 4 ladder + 7 ladder
    assert bench.sets[-1].weight_kg == 145
    assert bench.sets[-1].reps == 5
    # second exercise: weight-prefix `100 3*8` → 3 sets × 8 reps × 100 kg
    banded = result[1]
    assert "резин" in banded.raw_name.lower()
    assert len(banded.sets) == 3
    assert all(s.reps == 8 and s.weight_kg == 100 for s in banded.sets)


def test_weight_prefix_standalone() -> None:
    result = parse("жим 100 3*8")
    assert result is not None
    assert len(result[0].sets) == 3
    assert result[0].sets[0].weight_kg == 100
    assert result[0].sets[0].reps == 8


# ── Format C: name-only line + multiple continuations + multi-setgroup ──────

def test_format_c_name_only_plus_multi_setgroup() -> None:
    text = (
        "Становая сумо лямки\n"
        "20/60/100/130*5\n"
        "150/170/190*3\n"
        "210 2*2 220 1 * 2"
    )
    result = parse(text)
    assert result is not None
    assert len(result) == 1
    ex = result[0]
    assert "становая сумо" in ex.raw_name.lower()
    # 4 weights × 5 + 3 × 3 + 2 × 2 + 1 × 2 = 10 sets
    assert len(ex.sets) == 10
    weights = [s.weight_kg for s in ex.sets]
    assert weights == [20, 60, 100, 130, 150, 170, 190, 210, 210, 220]
    # last three sets are 2 reps
    assert [s.reps for s in ex.sets][-3:] == [2, 2, 2]


# ── Format D: N * R (spaces around operator), no weight ─────────────────────

def test_format_d_n_star_r_with_spaces() -> None:
    result = parse("Горизонтальня тяга 4 * 15")
    assert result is not None
    assert len(result) == 1
    ex = result[0]
    assert len(ex.sets) == 4
    assert all(s.weight_kg == 0.0 and s.reps == 15 for s in ex.sets)


def test_n_star_r_compact() -> None:
    result = parse("пуловер на блоке 4*20")
    assert result is not None
    assert len(result[0].sets) == 4
    assert all(s.reps == 20 and s.weight_kg == 0 for s in result[0].sets)


# ── Format E: multi-setgroup per line with "N по R" ─────────────────────────

def test_format_e_multi_setgroup_po() -> None:
    """Regression for data-corruption bug: `2 по 12 2 по 10` used to match
    `2 по 12 2` and capture the trailing 2 as weight=2kg, losing the second
    setgroup entirely.
    """
    result = parse("Бицепс с гантелями - 2 по 12 2 по 10")
    assert result is not None
    ex = result[0]
    assert "бицепс" in ex.raw_name.lower()
    # Expect 4 sets: 2 × 12 reps + 2 × 10 reps, all bodyweight (0 kg)
    assert len(ex.sets) == 4
    assert [s.reps for s in ex.sets] == [12, 12, 10, 10]
    assert all(s.weight_kg == 0.0 for s in ex.sets)


def test_multi_setgroup_weight_prefix_on_one_line() -> None:
    """`210 2*2 220 1*2` → 2 sets × 2 reps × 210 kg + 1 set × 2 reps × 220 kg."""
    result = parse("жим 210 2*2 220 1*2")
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 3
    assert [s.weight_kg for s in ex.sets] == [210, 210, 220]
    assert [s.reps for s in ex.sets] == [2, 2, 2]


def test_multi_setgroup_ladder_on_one_line() -> None:
    """Two ladders on one line — iterative matching should handle it."""
    result = parse("жим 20/40*10 60/80*8")
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 4
    assert [s.weight_kg for s in ex.sets] == [20, 40, 60, 80]
    assert [s.reps for s in ex.sets] == [10, 10, 8, 8]


# ── Pattern order regression: `3x8 80` must go to RE_NR_W, not RE_N_STAR_R ──

def test_pattern_order_3x8_80_keeps_weight() -> None:
    """If RE_N_STAR_R were tried before RE_NR_W, `3x8 80` would be parsed as
    3 weightless sets of 8 and the trailing weight would be lost. Guard it.
    """
    result = parse("жим 3x8 80")
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 3
    assert all(s.weight_kg == 80 and s.reps == 8 for s in ex.sets)


# ── RE_SETS_OF lookahead: weight group must not eat next `N по R` ──────────

def test_pause_modifier_full_message() -> None:
    """The exact message from the screenshot that triggered this fix."""
    text = (
        "Жим штанги лежа пауза 2с 20/50/80/110/110/120/120*5\n"
        "Тяга к животу 4 по 20\n"
        "Пуловер на блоке 4 по 20\n"
        "Сгибания голени 4 по 20\n"
        "Разгибания голени 4 по 15\n"
        "Махи на дельты 4 по 15\n"
        "Бицепс с гантелями 4 по 12\n"
        "Разгибания с канатом из-за головы 4 по 15"
    )
    result = parse(text)
    assert result is not None
    assert len(result) == 8
    # bench: 7-weight ladder × 5 reps
    bench = result[0]
    assert len(bench.sets) == 7
    assert [s.weight_kg for s in bench.sets] == [20, 50, 80, 110, 110, 120, 120]
    assert all(s.reps == 5 for s in bench.sets)
    # remaining 7 exercises: all bodyweight (0 kg) with varying reps
    for ex in result[1:]:
        assert len(ex.sets) == 4
        assert all(s.weight_kg == 0.0 for s in ex.sets)


def test_pause_with_descriptive_words_full_message() -> None:
    """Exact message from the screenshot: pause modifier with location word."""
    text = (
        "Присед оверхед 20/25/30/30*10 с паузой внизу 1сек\n"
        "Присед , штанга низко наколенники пояс20/60/90/120/120/140/140*8\n"
        "Тяга вертикальная в хаммере 4 по 20\n"
        "Сгибания голени 4 по 20\n"
        "Пуловер на блоке 4 по 20\n"
        "Трицепс из-за головы 4 по 15\n"
        "Бицепс с гантелями 4 по 12\n"
        "Махи на дельты 4 по 15\n"
        "Молитва на блоке 4 по 15"
    )
    result = parse(text)
    assert result is not None
    assert len(result) == 9
    # overhead squat: 4-weight ladder × 10 reps
    ohp = result[0]
    assert ohp.raw_name == "Присед оверхед"
    assert len(ohp.sets) == 4
    assert [s.weight_kg for s in ohp.sets] == [20, 25, 30, 30]
    assert all(s.reps == 10 for s in ohp.sets)
    # back squat: 7-weight ladder × 8 reps
    sq = result[1]
    assert len(sq.sets) == 7
    assert all(s.reps == 8 for s in sq.sets)


def test_single_weight_star_reps_continuation() -> None:
    """220 *2 after a ladder → 1 set of 2 reps at 220 kg, not 220 bodyweight sets."""
    text = (
        "Присед, штанга низко наколенники пояс 20/60/100*5\n"
        "120/135/150/165*4\n"
        "180/190/200/210*3\n"
        "220 *2"
    )
    result = parse(text)
    assert result is not None
    assert len(result) == 1
    ex = result[0]
    # 3 + 4 + 4 + 1 = 12 sets
    assert len(ex.sets) == 12
    last = ex.sets[-1]
    assert last.weight_kg == 220.0
    assert last.reps == 2


def test_single_weight_star_reps_standalone() -> None:
    """Standalone 220*2 without ladder context."""
    result = parse("присед 220*2")
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 1
    assert ex.sets[0].weight_kg == 220.0
    assert ex.sets[0].reps == 2


def test_rep_range_w_nr() -> None:
    """90 3*8-12 → weight=90, 3 sets of 8 reps (lower bound kept, range discarded)."""
    result = parse("Фронтальный присед 90 3*8-12")
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 3
    assert all(s.weight_kg == 90 and s.reps == 8 for s in ex.sets)


def test_rep_range_n_star_r() -> None:
    """4*8-12 bodyweight → 4 sets of 8."""
    result = parse("подтягивания 4*8-12")
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 4
    assert all(s.reps == 8 and s.weight_kg == 0 for s in ex.sets)


def test_rep_range_sets_of() -> None:
    """4 по 10-15 → 4 sets of 10."""
    result = parse("махи на дельты 4 по 10-15")
    assert result is not None
    ex = result[0]
    assert len(ex.sets) == 4
    assert all(s.reps == 10 for s in ex.sets)


def test_sets_of_lookahead_blocks_greedy_weight() -> None:
    """Bare regression test for the specific weight-greediness bug."""
    # Two groups separated by space — weight slot should not eat leading 2 from second.
    result = parse("пресс 2 по 15 2 по 10")
    assert result is not None
    ex = result[0]
    # 2×15 + 2×10 = 4 bodyweight sets
    assert len(ex.sets) == 4
    assert [s.reps for s in ex.sets] == [15, 15, 10, 10]
    assert all(s.weight_kg == 0.0 for s in ex.sets)
