"""Smoke test: build the dispatcher with all routers and assert handlers are registered."""

from __future__ import annotations

import aiosqlite
import pytest

from pwrbot.bot.app import build_dispatcher
from pwrbot.bot.formatting import (
    format_analysis,
    format_ingest_reply,
    format_week_summary,
)
from pwrbot.db.connection import bootstrap
from pwrbot.domain.catalog import load_catalog
from pwrbot.domain.models import ExercisePayload, SetPayload, WorkoutPayload
from pwrbot.parsing.pipeline import ParsingPipeline
from pwrbot.services.analyze import AnalyzeResult, AnalyzeService
from pwrbot.services.ingest import IngestService
from tests.conftest import REPO_ROOT


@pytest.fixture
async def conn():
    c = await aiosqlite.connect(":memory:")
    c.row_factory = aiosqlite.Row
    await c.execute("PRAGMA foreign_keys = ON")
    await bootstrap(c)
    try:
        yield c
    finally:
        await c.close()


async def test_dispatcher_builds_with_all_routers(conn, yaml_config) -> None:
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    pipeline = ParsingPipeline(catalog=catalog, cfg=yaml_config, llm_parser=None)
    analyzer = AnalyzeService(cfg=yaml_config, llm=None)
    ingest = IngestService(
        pipeline=pipeline, analyzer=analyzer, catalog=catalog, cfg=yaml_config
    )

    dp = build_dispatcher(
        conn=conn,
        ingest=ingest,
        analyze=analyzer,
    )

    # 6 routers expected: basic, view, analyze, edit, clarify, log
    assert len(dp.sub_routers) == 6


def test_format_parsed_workout_basic() -> None:
    payload = WorkoutPayload(
        exercises=[
            ExercisePayload(
                raw_name="присед",
                canonical_name="back_squat",
                sets=[
                    SetPayload(reps=5, weight_kg=100.0, rpe=8.0),
                    SetPayload(reps=5, weight_kg=100.0, rpe=8.0),
                ],
            )
        ]
    )
    out = format_ingest_reply(payload, None)
    assert "back_squat" in out
    assert "5×100кг" in out
    assert "@8" in out


def test_format_week_summary_empty() -> None:
    assert "нет" in format_week_summary([]).lower()


def test_format_analysis_no_flags() -> None:
    result = AnalyzeResult(
        window_days=7,
        metrics={
            "window": {
                "total_tonnage_kg": 1234.0,
                "total_hard_sets": 10,
                "hard_sets_by_pattern": {"push": 5, "pull": 5},
            }
        },
        flags=[],
        explanation="всё норм",
        snapshot_id=1,
    )
    out = format_analysis(result)
    assert "Флагов нет" in out
    assert "1234" in out
    assert "всё норм" in out
