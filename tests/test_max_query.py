"""Tests for free-form max question detection, parsing, and service."""

from __future__ import annotations

import time

import pytest

from pwrbot.config import YamlConfig
from pwrbot.db import repo
from pwrbot.db.repo import ExerciseRow, SetRow
from pwrbot.domain.catalog import load_catalog
from pwrbot.services.max_query import MaxQueryService, try_parse_max_question
from tests.conftest import REPO_ROOT

# ------------------------------------------------------------------ detection


@pytest.mark.parametrize(
    "text",
    [
        "какой у меня максимум на присед",
        "какой максимум на жим лежа",
        "мой максимум в становой",
        "сколько жму на раз",
        "какой рекорд на жиме",
        "мой рм на присед",
        "какой мой 1rm присед",
        "е1рм присед",
        "e1rm жим",
        "5рм в приседе",
        "какой у меня максимум на присед на 5 повторений?",
        "покажи макс на становой",
        "скажи максимум на жим на 3 раза",
    ],
)
def test_detects_max_question(text: str):
    result = try_parse_max_question(text)
    assert result is not None, f"Failed to detect max question: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "присед 4x5x100",
        "жим 3x8x80 rpe8",
        "становая 180/190/200*3",
        "20/40/60/80/100*5",
        "Бицепс 3 по 12",
        "",
        "привет",
        "тренировка сегодня была тяжелая",
    ],
)
def test_rejects_non_question(text: str):
    result = try_parse_max_question(text)
    assert result is None, f"False positive on: {text!r}"


# ------------------------------------------------------------------ reps extraction


def test_extracts_reps_na_N_povtoreniy():
    q = try_parse_max_question("какой максимум на присед на 5 повторений")
    assert q is not None
    assert q.reps == 5


def test_extracts_reps_Nrm():
    q = try_parse_max_question("5рм в приседе")
    assert q is not None
    assert q.reps == 5


def test_extracts_reps_na_N_raz():
    q = try_parse_max_question("какой максимум на жим на 3 раза")
    assert q is not None
    assert q.reps == 3


def test_default_reps_1():
    q = try_parse_max_question("какой максимум на присед")
    assert q is not None
    assert q.reps == 1


def test_extracts_exercise_name():
    q = try_parse_max_question("какой максимум на жим лежа")
    assert q is not None
    assert "жим" in q.raw_exercise.lower()


# ------------------------------------------------------------------ service (integration)


async def test_answer_1rm(conn, yaml_config: YamlConfig):
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    svc = MaxQueryService(catalog=catalog, cfg=yaml_config)

    uid = await repo.get_or_create_user(conn, telegram_id=42)
    # Insert a workout with squat
    await repo.insert_workout(
        conn,
        user_id=uid,
        performed_at=int(time.time()) - 86_400,
        source_text="присед 5x5x140",
        exercises=[
            ExerciseRow(
                position=1,
                raw_name="присед",
                canonical_name="back_squat",
                movement_pattern="squat",
                sets=[
                    SetRow(reps=5, weight_g=140_000, rpe=None, is_warmup=False, set_index=i)
                    for i in range(1, 6)
                ],
            ),
        ],
    )

    q = try_parse_max_question("какой максимум на присед")
    assert q is not None
    reply = await svc.answer(conn, user_id=uid, query=q)
    assert "присед" in reply
    assert "кг" in reply
    assert "140" in reply


async def test_answer_nrm(conn, yaml_config: YamlConfig):
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    svc = MaxQueryService(catalog=catalog, cfg=yaml_config)

    uid = await repo.get_or_create_user(conn, telegram_id=42)
    await repo.insert_workout(
        conn,
        user_id=uid,
        performed_at=int(time.time()) - 86_400,
        source_text="жим 3x3x100",
        exercises=[
            ExerciseRow(
                position=1,
                raw_name="жим",
                canonical_name="bench_press",
                movement_pattern="push",
                sets=[
                    SetRow(reps=3, weight_g=100_000, rpe=None, is_warmup=False, set_index=i)
                    for i in range(1, 4)
                ],
            ),
        ],
    )

    q = try_parse_max_question("какой максимум на жим на 5 повторений")
    assert q is not None
    assert q.reps == 5
    reply = await svc.answer(conn, user_id=uid, query=q)
    assert "5RM" in reply
    assert "жим" in reply
    assert "кг" in reply


async def test_answer_no_data(conn, yaml_config: YamlConfig):
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    svc = MaxQueryService(catalog=catalog, cfg=yaml_config)

    uid = await repo.get_or_create_user(conn, telegram_id=42)
    q = try_parse_max_question("какой максимум на присед")
    assert q is not None
    reply = await svc.answer(conn, user_id=uid, query=q)
    assert "Нет данных" in reply


async def test_answer_unknown_exercise(conn, yaml_config: YamlConfig):
    catalog = load_catalog(REPO_ROOT / "config" / "exercises.yaml")
    svc = MaxQueryService(catalog=catalog, cfg=yaml_config)

    uid = await repo.get_or_create_user(conn, telegram_id=42)
    from pwrbot.services.max_query import MaxQuery
    q = MaxQuery(raw_exercise="несуществующее упражнение", reps=1)
    reply = await svc.answer(conn, user_id=uid, query=q)
    assert "Не нашёл" in reply
