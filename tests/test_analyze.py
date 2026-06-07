from __future__ import annotations

import asyncio
import time

from pwrbot.db import repo
from pwrbot.db.repo import ExerciseRow, SetRow
from pwrbot.services.analyze import AnalyzeService


class _SlowLLM:
    def __init__(self, delay_s: float) -> None:
        self.delay_s = delay_s
        self.explain_calls = 0
        self.render_calls = 0
        self.explain_metrics = None
        self.render_metrics = None

    async def explain(self, *, metrics, flags, window_days) -> str:
        self.explain_calls += 1
        self.explain_metrics = metrics
        await asyncio.sleep(self.delay_s)
        return "gemma explanation"

    def render_explain_prompt(self, *, metrics, flags, window_days) -> tuple[str, str]:
        self.render_calls += 1
        self.render_metrics = metrics
        return "system prompt", "user prompt"


class _SlowCodex:
    def __init__(self, delay_s: float) -> None:
        self.delay_s = delay_s
        self.calls: list[tuple[str, str, float]] = []

    async def explain(self, system: str, user: str, *, timeout_s: float) -> str:
        self.calls.append((system, user, timeout_s))
        await asyncio.sleep(self.delay_s)
        return "codex explanation"


async def test_analyze_dual_explain_parallel(conn, yaml_config) -> None:
    uid = await repo.get_or_create_user(conn, telegram_id=42)
    llm = _SlowLLM(delay_s=0.10)
    codex = _SlowCodex(delay_s=0.10)
    svc = AnalyzeService(cfg=yaml_config, llm=llm, codex=codex)  # type: ignore[arg-type]

    started_at = time.monotonic()
    result = await svc.analyze(conn, user_id=uid, window_days=7)
    elapsed_s = time.monotonic() - started_at

    assert result.explanation_gemma.text == "gemma explanation"
    assert result.explanation_codex.text == "codex explanation"
    assert result.explanation_gemma.latency_s is not None
    assert result.explanation_gemma.latency_s > 0
    assert result.explanation_codex.latency_s is not None
    assert result.explanation_codex.latency_s > 0
    assert elapsed_s < 0.18
    assert codex.calls == [("system prompt", "user prompt", yaml_config.llm.codex.timeout_s)]

    assert llm.explain_calls == 1
    assert llm.render_calls == 1

    row = await (
        await conn.execute("SELECT explanation FROM analysis_snapshots WHERE id = ?", (result.snapshot_id,))
    ).fetchone()
    assert row["explanation"] == "gemma explanation"


async def test_analyze_codex_only_when_gemma_disabled(conn, yaml_config) -> None:
    uid = await repo.get_or_create_user(conn, telegram_id=43)
    llm = _SlowLLM(delay_s=0.01)
    codex = _SlowCodex(delay_s=0.01)
    svc = AnalyzeService(
        cfg=yaml_config,
        llm=llm,  # type: ignore[arg-type]
        codex=codex,  # type: ignore[arg-type]
        gemma_enabled=False,
    )

    result = await svc.analyze(conn, user_id=uid, window_days=7)

    assert result.explanation_gemma.text is None
    assert result.explanation_gemma.error == "disabled"
    assert result.explanation_codex.text == "codex explanation"
    assert llm.explain_calls == 0
    assert llm.render_calls == 1
    assert codex.calls == [("system prompt", "user prompt", yaml_config.llm.codex.timeout_s)]

    row = await (
        await conn.execute("SELECT explanation FROM analysis_snapshots WHERE id = ?", (result.snapshot_id,))
    ).fetchone()
    assert row["explanation"] == "codex explanation"


async def test_analyze_explain_prompt_gets_recent_workout_context(conn, yaml_config) -> None:
    uid = await repo.get_or_create_user(conn, telegram_id=44)
    now_ts = int(time.time())
    await repo.insert_workout(
        conn,
        user_id=uid,
        performed_at=now_ts - 86_400,
        source_text="жим лежа 4x5x100, тяга вертикальная 4x10x70",
        exercises=[
            ExerciseRow(
                position=1,
                raw_name="жим лежа",
                canonical_name="bench_press",
                movement_pattern="push",
                sets=[
                    SetRow(reps=5, weight_g=100_000, rpe=8.0, is_warmup=False, set_index=i)
                    for i in range(1, 5)
                ],
            ),
            ExerciseRow(
                position=2,
                raw_name="тяга вертикальная",
                canonical_name="lat_pulldown",
                movement_pattern="pull",
                sets=[
                    SetRow(reps=10, weight_g=70_000, rpe=8.0, is_warmup=False, set_index=i)
                    for i in range(1, 5)
                ],
            ),
        ],
    )
    llm = _SlowLLM(delay_s=0)
    svc = AnalyzeService(cfg=yaml_config, llm=llm, codex=None)  # type: ignore[arg-type]

    result = await svc.analyze(conn, user_id=uid, window_days=7)

    assert llm.explain_metrics is not None
    context = llm.explain_metrics["training_context"]
    assert context["recent_workouts_count"] == 1
    assert context["recent_workouts"][0]["source_text"] == "жим лежа 4x5x100, тяга вертикальная 4x10x70"
    assert context["recent_workouts"][0]["exercises"] == [
        {
            "name": "bench_press",
            "movement_pattern": "push",
            "working_sets": 4,
            "hard_sets": 4,
            "top_set": "5×100кг @8",
        },
        {
            "name": "lat_pulldown",
            "movement_pattern": "pull",
            "working_sets": 4,
            "hard_sets": 4,
            "top_set": "10×70кг @8",
        },
    ]
    assert result.metrics["training_context"] == context
