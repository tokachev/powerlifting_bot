"""Shared pytest fixtures: in-memory sqlite, sample workouts, yaml config stub."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from pwrbot.config import (
    BalanceThresholds,
    HardSetThresholds,
    LLMConfig,
    RecoveryThresholds,
    Thresholds,
    WarmupThresholds,
    Windows,
    YamlConfig,
)
from pwrbot.db.connection import bootstrap

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
async def conn():
    """In-memory SQLite connection with the schema bootstrapped.

    Shared by integration / API / reporting tests.
    """
    c = await aiosqlite.connect(":memory:")
    c.row_factory = aiosqlite.Row
    await c.execute("PRAGMA foreign_keys = ON")
    await bootstrap(c)
    try:
        yield c
    finally:
        await c.close()


@pytest.fixture
def yaml_config() -> YamlConfig:
    return YamlConfig(
        windows=Windows(short_days=7, long_days=28),
        thresholds=Thresholds(
            hard_set=HardSetThresholds(min_rpe=7.0, intensity_fraction=0.75),
            balance=BalanceThresholds(
                push_pull_target=1.0,
                squat_hinge_target=1.0,
                tolerance=0.30,
                min_hard_sets_for_flag=5,
            ),
            recovery=RecoveryThresholds(
                max_hard_sets_7d={"squat": 12, "hinge": 10, "push": 16, "pull": 18},
                tonnage_spike_ratio=1.5,
            ),
            warmup=WarmupThresholds(max_fraction_of_working_weight=0.60),
        ),
        llm=LLMConfig(),
    )


@pytest.fixture
def now_ts() -> int:
    """Fixed 'now' timestamp for deterministic window tests."""
    return int(datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC).timestamp())
