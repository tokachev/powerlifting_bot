"""Integration tests for the full /log → auto-analyze flow with mocked LLM,
including the pending-clarification branch when the canonicalizer can't resolve."""

from __future__ import annotations

from datetime import UTC, datetime

from pwrbot.db import repo
from pwrbot.domain.catalog import load_catalog
from pwrbot.parsing.llm_parser import CanonicalizeResult
from pwrbot.parsing.pipeline import ParsingPipeline
from pwrbot.services.analyze import AnalyzeService
from pwrbot.services.ingest import IngestService, PendingClarification
from tests.conftest import REPO_ROOT


class _StubLLM:
    """Configurable LLM stub.

    - `canon_response_for`: maps raw_name → CanonicalizeResult. Falls back to
      an empty result (null canonical, no suggestions) for unknown inputs.
    """

    def __init__(self, canon_response_for: dict[str, CanonicalizeResult] | None = None) -> None:
        self.calls: list[str] = []
        self._canon = canon_response_for or {}

    async def parse_text(self, text: str):  # pragma: no cover — regex handles test inputs
        raise RuntimeError("regex should handle this test input")

    async def canonicalize(self, raw_name: str) -> CanonicalizeResult:
        self.calls.append(raw_name)
        return self._canon.get(raw_name, CanonicalizeResult())

    async def explain(self, *, metrics, flags, window_days) -> str:
        return f"fake explanation for {window_days}d, flags={len(flags)}"


def _make_services(catalog, yaml_config, llm):
    pipeline = ParsingPipeline(catalog=catalog, cfg=yaml_config, llm_parser=llm)  # type: ignore[arg-type]
    analyzer = AnalyzeService(cfg=yaml_config, llm=llm)  # type: ignore[arg-type]
    ingest = IngestService(
        pipeline=pipeline, analyzer=analyzer, catalog=catalog, cfg=yaml_config
    )
    return pipeline, analyzer, ingest


async def test_log_then_auto_analyze(conn, yaml_config) -> None:
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM()
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    result = await ingest.ingest(
        conn,
        user_id=uid,
        source_text="присед 4x5x100 rpe8\nжим 3x8x80",
    )

    assert result.parse_error is None
    assert result.pending is None
    assert result.workout_id > 0
    assert len(result.payload.exercises) == 2
    assert result.payload.exercises[0].canonical_name == "back_squat"
    assert result.payload.exercises[1].canonical_name == "bench_press"
    assert llm.calls == []  # catalog resolved both

    assert result.analysis is not None
    assert result.analysis.window_days == 7
    assert result.analysis.explanation == "fake explanation for 7d, flags=0"
    row = await (
        await conn.execute("SELECT COUNT(*) AS c FROM analysis_snapshots")
    ).fetchone()
    assert row["c"] == 1

    # 1RM estimates should be populated for big-3 exercises
    assert len(result.rm_estimates) == 2
    names = {e.canonical_name for e in result.rm_estimates}
    assert "back_squat" in names
    assert "bench_press" in names
    squat_est = next(e for e in result.rm_estimates if e.canonical_name == "back_squat")
    assert squat_est.target_group == "squat"
    assert squat_est.estimated_1rm_kg > 100  # must be > the working weight


async def test_log_unknown_exercise_returns_pending(conn, yaml_config) -> None:
    """Unknown raw_name → LLM returns suggestions → service returns pending, no persist."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM(
        canon_response_for={
            "шраги": CanonicalizeResult(
                canonical_name=None, suggestions=["barbell_row", "dumbbell_row", "seated_row"]
            ),
        }
    )
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    result = await ingest.ingest(conn, user_id=uid, source_text="шраги 4x10x60")

    assert result.parse_error is None
    assert result.pending is not None
    assert result.workout_id == 0
    assert result.analysis is None
    # nothing persisted
    row = await (
        await conn.execute("SELECT COUNT(*) AS c FROM workouts")
    ).fetchone()
    assert row["c"] == 0

    # pending has one unresolved exercise with suggestions
    assert len(result.pending.unresolved) == 1
    u = result.pending.unresolved[0]
    assert u.raw_name == "шраги"
    assert u.suggestions == ["barbell_row", "dumbbell_row", "seated_row"]


async def test_log_llm_confident_canonical_persists(conn, yaml_config) -> None:
    """Unknown raw_name → LLM returns a confident canonical → persist happens."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM(
        canon_response_for={
            "шраги": CanonicalizeResult(canonical_name="barbell_row", suggestions=[]),
        }
    )
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    result = await ingest.ingest(conn, user_id=uid, source_text="шраги 4x10x60")
    assert result.pending is None
    assert result.workout_id > 0
    assert result.payload.exercises[0].canonical_name == "barbell_row"


async def test_finalize_pending_after_user_choice(conn, yaml_config) -> None:
    """Simulate the clarify callback: patch the pending payload with a user
    choice, then call finalize_pending and assert full persist + analyze."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM(
        canon_response_for={
            "шраги": CanonicalizeResult(canonical_name=None, suggestions=["barbell_row"]),
        }
    )
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    result = await ingest.ingest(conn, user_id=uid, source_text="шраги 4x10x60")
    assert result.pending is not None

    # User picks "barbell_row" — handler patches the payload.
    pending = result.pending
    idx = pending.unresolved[0].index
    exercises = list(pending.payload.exercises)
    exercises[idx] = exercises[idx].model_copy(update={"canonical_name": "barbell_row"})
    pending = pending.model_copy(
        update={"payload": pending.payload.model_copy(update={"exercises": exercises})}
    )

    final = await ingest.finalize_pending(conn, user_id=uid, pending=pending)
    assert final.workout_id > 0
    assert final.payload.exercises[0].canonical_name == "barbell_row"
    assert final.analysis is not None
    # Now the exercise counts toward the "pull" pattern
    window = final.analysis.metrics["window"]
    assert window["working_sets_by_pattern"].get("pull", 0) == 4


async def test_format_a_ladder_continuation(conn, yaml_config) -> None:
    """Format A: one exercise across two ladder lines + comma in name modifier."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM()
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    text = (
        "Присед , штанга низко наколенники пояс20/60/90/120*5\n"
        "140/145/150/155*8"
    )
    result = await ingest.ingest(conn, user_id=uid, source_text=text)
    assert result.parse_error is None
    assert result.pending is None
    assert len(result.payload.exercises) == 1
    ex = result.payload.exercises[0]
    assert ex.canonical_name == "back_squat"
    # 4 warmup-ish + 4 working sets = 8 sets, last working=155
    assert len(ex.sets) == 8
    # warmup rule: max=155, threshold=93 → 20/60/90 are warmup
    warmup_weights = [s.weight_kg for s in ex.sets if s.is_warmup]
    assert warmup_weights == [20, 60, 90]


async def test_format_b_weight_prefix_and_banded(conn, yaml_config) -> None:
    """Format B: ladder continuation + weight-prefix on second exercise."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM()
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    text = (
        "Жим штанги лежа 20/50/80/110*12\n"
        "115/120/125/130/135/140/145*5\n"
        "Жим с резиной 100 3*8"
    )
    result = await ingest.ingest(conn, user_id=uid, source_text=text)
    assert result.parse_error is None
    assert result.pending is None
    assert len(result.payload.exercises) == 2
    assert result.payload.exercises[0].canonical_name == "bench_press"
    # Banded bench merges into bench_press (tech-debt decision)
    assert result.payload.exercises[1].canonical_name == "bench_press"
    banded = result.payload.exercises[1]
    assert len(banded.sets) == 3
    assert all(s.weight_kg == 100 and s.reps == 8 for s in banded.sets)


async def test_format_c_sumo_with_multi_setgroup(conn, yaml_config) -> None:
    """Format C: name-only header + 3 continuation lines + multi-setgroup per line."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM()
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    text = (
        "Становая сумо лямки\n"
        "20/60/100/130*5\n"
        "150/170/190*3\n"
        "210 2*2 220 1 * 2"
    )
    result = await ingest.ingest(conn, user_id=uid, source_text=text)
    assert result.parse_error is None
    assert result.pending is None
    ex = result.payload.exercises[0]
    assert ex.canonical_name == "sumo_deadlift"
    assert len(ex.sets) == 10
    # Warmup rule: max=220, threshold=132 → warmup=[20, 60, 100, 130]
    warmup_weights = [s.weight_kg for s in ex.sets if s.is_warmup]
    assert warmup_weights == [20, 60, 100, 130]


async def test_format_e_multi_setgroup_po(conn, yaml_config) -> None:
    """Format E regression: `2 по 12 2 по 10` corruption bug."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM()
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    result = await ingest.ingest(
        conn, user_id=uid, source_text="Бицепс с гантелями - 2 по 12 2 по 10"
    )
    assert result.parse_error is None
    assert result.pending is None
    ex = result.payload.exercises[0]
    assert ex.canonical_name == "dumbbell_bicep_curl"
    assert len(ex.sets) == 4
    assert [s.reps for s in ex.sets] == [12, 12, 10, 10]
    assert all(s.weight_kg == 0 for s in ex.sets)


async def test_format_g_header_date_override(conn, yaml_config) -> None:
    """Header date: first line `8 марта` sets performed_at to that date."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM()
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    result = await ingest.ingest(
        conn, user_id=uid, source_text="8 марта\nМахи на дельты 4 * 15"
    )
    assert result.parse_error is None
    assert result.pending is None
    ex = result.payload.exercises[0]
    assert ex.canonical_name == "lateral_raise"
    assert len(ex.sets) == 4
    assert all(s.weight_kg == 0 and s.reps == 15 for s in ex.sets)
    # Header date: past March 8 (either this year or last)
    assert result.payload.performed_at is not None
    assert result.payload.performed_at.month == 3
    assert result.payload.performed_at.day == 8
    now = datetime.now(UTC)
    assert result.payload.performed_at <= now


async def test_append_to_last_extends_existing_workout(conn, yaml_config) -> None:
    """/add path: parse new text and append to the most recent workout instead
    of inserting a new one. Source text must concat; positions must extend."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM()
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    first = await ingest.ingest(conn, user_id=uid, source_text="присед 4x5x100")
    assert first.workout_id > 0

    appended = await ingest.append_to_last(
        conn, user_id=uid, source_text="жим 3x8x80",
    )
    assert appended.parse_error is None
    assert appended.pending is None
    assert appended.was_append is True
    assert appended.workout_id == first.workout_id

    # Still exactly one workout row, but with both exercises.
    row = await (await conn.execute("SELECT COUNT(*) AS c FROM workouts")).fetchone()
    assert row["c"] == 1
    last = await repo.get_last_workout(conn, user_id=uid)
    assert last is not None
    assert [ex.canonical_name for ex in last.exercises] == ["back_squat", "bench_press"]
    assert [ex.position for ex in last.exercises] == [1, 2]
    assert last.source_text == "присед 4x5x100\nжим 3x8x80"


async def test_append_to_last_with_no_workout(conn, yaml_config) -> None:
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM()
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    result = await ingest.append_to_last(
        conn, user_id=uid, source_text="присед 4x5x100",
    )
    assert result.workout_id == 0
    assert result.parse_error is not None
    assert "Нет тренировок" in result.parse_error


async def test_append_pending_then_finalize(conn, yaml_config) -> None:
    """Append + clarify: unresolved exercise → pending with target_workout_id;
    finalize_pending must append (not insert) and report was_append=True."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM(
        canon_response_for={
            "шраги": CanonicalizeResult(canonical_name=None, suggestions=["barbell_row"]),
        }
    )
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    first = await ingest.ingest(conn, user_id=uid, source_text="присед 4x5x100")

    pend_result = await ingest.append_to_last(
        conn, user_id=uid, source_text="шраги 4x10x60",
    )
    assert pend_result.pending is not None
    assert pend_result.pending.target_workout_id == first.workout_id

    pending = pend_result.pending
    idx = pending.unresolved[0].index
    exercises = list(pending.payload.exercises)
    exercises[idx] = exercises[idx].model_copy(update={"canonical_name": "barbell_row"})
    pending = pending.model_copy(
        update={"payload": pending.payload.model_copy(update={"exercises": exercises})}
    )

    final = await ingest.finalize_pending(conn, user_id=uid, pending=pending)
    assert final.was_append is True
    assert final.workout_id == first.workout_id

    row = await (await conn.execute("SELECT COUNT(*) AS c FROM workouts")).fetchone()
    assert row["c"] == 1
    last = await repo.get_last_workout(conn, user_id=uid)
    assert last is not None
    assert [ex.canonical_name for ex in last.exercises] == ["back_squat", "barbell_row"]


async def test_append_pending_workout_deleted_before_finalize(conn, yaml_config) -> None:
    """If the user deletes the target workout before answering clarify buttons,
    finalize_pending must surface a clean parse_error instead of crashing on FK."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM(
        canon_response_for={
            "шраги": CanonicalizeResult(canonical_name=None, suggestions=["barbell_row"]),
        }
    )
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    await ingest.ingest(conn, user_id=uid, source_text="присед 4x5x100")
    pend_result = await ingest.append_to_last(
        conn, user_id=uid, source_text="шраги 4x10x60",
    )
    pending = pend_result.pending
    assert pending is not None

    await repo.delete_last_workout(conn, user_id=uid)
    final = await ingest.finalize_pending(conn, user_id=uid, pending=pending)
    assert final.workout_id == 0
    assert final.parse_error is not None
    assert "удалена" in final.parse_error


async def test_pending_serializes_roundtrip(conn, yaml_config) -> None:
    """PendingClarification must JSON-round-trip for FSM storage."""
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    llm = _StubLLM(
        canon_response_for={
            "шраги": CanonicalizeResult(canonical_name=None, suggestions=["barbell_row"]),
        }
    )
    _, _, ingest = _make_services(catalog, yaml_config, llm)

    uid = await repo.get_or_create_user(conn, telegram_id=1)
    result = await ingest.ingest(conn, user_id=uid, source_text="шраги 4x10x60")
    assert result.pending is not None

    raw = result.pending.model_dump_json()
    restored = PendingClarification.model_validate_json(raw)
    assert restored.source_text == result.pending.source_text
    assert restored.unresolved[0].suggestions == ["barbell_row"]
