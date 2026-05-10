from __future__ import annotations

import asyncio
import time

from pwrbot.db import repo
from pwrbot.services.analyze import AnalyzeService


class _SlowLLM:
    def __init__(self, delay_s: float) -> None:
        self.delay_s = delay_s

    async def explain(self, *, metrics, flags, window_days) -> str:
        await asyncio.sleep(self.delay_s)
        return "gemma explanation"

    def render_explain_prompt(self, *, metrics, flags, window_days) -> tuple[str, str]:
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

    row = await (
        await conn.execute("SELECT explanation FROM analysis_snapshots WHERE id = ?", (result.snapshot_id,))
    ).fetchone()
    assert row["explanation"] == "gemma explanation"
