"""/1rm, /stats, /prs, /volume bot commands."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import aiosqlite
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from pwrbot.bot.formatting import _BIG3_DISPLAY, _fmt_weight
from pwrbot.config import YamlConfig
from pwrbot.db import repo
from pwrbot.domain.catalog import Catalog
from pwrbot.metrics.weekly_sets import compute_weekly_sets
from pwrbot.rules.one_rm import compute_1rm_estimates, estimate_1rm, find_best_set
from pwrbot.rules.volume import compute as compute_volume

router = Router()

DAY_S = 86_400


def _display(canonical: str) -> str:
    return _BIG3_DISPLAY.get(canonical, canonical.replace("_", " "))


# ------------------------------------------------------------------ /1rm


@router.message(Command("1rm"))
async def cmd_1rm(
    message: Message,
    command: CommandObject,
    conn: aiosqlite.Connection,
    catalog: Catalog,
    yaml_config: YamlConfig,
) -> None:
    if message.from_user is None:
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    now_ts = int(time.time())
    rm_days = yaml_config.windows.rm_window_days

    history = await repo.get_workouts_in_window(
        conn, user_id=uid,
        since_ts=now_ts - rm_days * DAY_S,
        until_ts=now_ts,
    )

    if command.args and command.args.strip():
        entry = catalog.resolve(command.args.strip())
        if entry is None:
            await message.answer(f"Не нашёл упражнение «{command.args.strip()}» в каталоге.")
            return
        best = find_best_set(history, entry.canonical_name)
        if best is None:
            await message.answer(f"Нет данных по «{_display(entry.canonical_name)}» за {rm_days}д.")
            return
        weight_kg, reps = best
        e1rm = estimate_1rm(weight_kg, reps)
        await message.answer(
            f"{_display(entry.canonical_name)}: e1RM ~{_fmt_weight(e1rm)} кг "
            f"(на основе {_fmt_weight(weight_kg)}×{reps})"
        )
        return

    # No argument: show all big-3
    target_exercises: list[tuple[str, str | None]] = []
    for e in catalog.entries:
        if e.target_group is not None:
            target_exercises.append((e.canonical_name, e.target_group))

    estimates = compute_1rm_estimates(history, target_exercises)
    if not estimates:
        await message.answer(f"Нет данных за {rm_days} дней.")
        return

    lines = ["Расчётный 1RM:"]
    for e in estimates:
        lines.append(
            f"  {_display(e.canonical_name)}: ~{_fmt_weight(e.estimated_1rm_kg)} кг "
            f"(на основе {_fmt_weight(e.best_set_weight_kg)}×{e.best_set_reps})"
        )
    await message.answer("\n".join(lines))


# ------------------------------------------------------------------ /stats


@router.message(Command("stats"))
async def cmd_stats(
    message: Message,
    conn: aiosqlite.Connection,
    catalog: Catalog,
    yaml_config: YamlConfig,
) -> None:
    if message.from_user is None:
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    now_ts = int(time.time())

    history = await repo.get_workouts_in_window(
        conn, user_id=uid,
        since_ts=now_ts - 7 * DAY_S,
        until_ts=now_ts,
    )

    if not history:
        await message.answer("Нет тренировок за 7 дней.")
        return

    metrics = compute_volume(history, yaml_config.thresholds)

    lines = [f"Статистика за 7 дней ({len(history)} тренировок):"]
    lines.append(f"  тоннаж: {_fmt_weight(metrics.total_tonnage_kg)} кг")
    lines.append(f"  рабочих сетов: {metrics.total_working_sets}")
    lines.append(f"  hard-сетов: {metrics.total_hard_sets}")

    if metrics.hard_sets_by_pattern:
        parts = ", ".join(f"{k}: {v}" for k, v in sorted(metrics.hard_sets_by_pattern.items()))
        lines.append(f"  по паттернам: {parts}")

    # Add e1RM for big-3
    rm_history = await repo.get_workouts_in_window(
        conn, user_id=uid,
        since_ts=now_ts - yaml_config.windows.rm_window_days * DAY_S,
        until_ts=now_ts,
    )
    target_exercises: list[tuple[str, str | None]] = []
    for e in catalog.entries:
        if e.target_group is not None:
            target_exercises.append((e.canonical_name, e.target_group))
    estimates = compute_1rm_estimates(rm_history, target_exercises)
    if estimates:
        lines.append("")
        lines.append("Расчётный 1RM:")
        for e in estimates:
            lines.append(f"  {_display(e.canonical_name)}: ~{_fmt_weight(e.estimated_1rm_kg)} кг")

    await message.answer("\n".join(lines))


# ------------------------------------------------------------------ /prs


@router.message(Command("prs"))
async def cmd_prs(
    message: Message,
    conn: aiosqlite.Connection,
) -> None:
    if message.from_user is None:
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)

    records = await repo.get_personal_records(conn, user_id=uid, limit=10)
    if not records:
        await message.answer("Рекордов пока нет.")
        return

    lines = ["Последние рекорды:"]
    for r in records:
        d = datetime.fromtimestamp(r.achieved_at, tz=UTC).strftime("%d.%m")
        name = _display(r.canonical_name)
        e1rm = r.estimated_1rm_g / 1000.0
        weight = r.weight_g / 1000.0
        delta = ""
        if r.previous_value_g is not None:
            diff = e1rm - r.previous_value_g / 1000.0
            delta = f" (+{_fmt_weight(diff)})"
        lines.append(
            f"  {d} {name}: {_fmt_weight(weight)}×{r.reps} → "
            f"e1RM ~{_fmt_weight(e1rm)} кг{delta}"
        )
    await message.answer("\n".join(lines))


# ------------------------------------------------------------------ /volume


@router.message(Command("volume"))
async def cmd_volume(
    message: Message,
    conn: aiosqlite.Connection,
    catalog: Catalog,
    yaml_config: YamlConfig,
) -> None:
    if message.from_user is None:
        return
    uid = await repo.get_or_create_user(conn, telegram_id=message.from_user.id)
    now_ts = int(time.time())

    history = await repo.get_workouts_in_window(
        conn, user_id=uid,
        since_ts=now_ts - 7 * DAY_S,
        until_ts=now_ts,
    )

    if not history:
        await message.answer("Нет тренировок за 7 дней.")
        return

    buckets = compute_weekly_sets(history, catalog, yaml_config.thresholds)
    landmarks = yaml_config.volume_landmarks

    # aggregate across the week (could span 2 ISO weeks, sum them)
    totals: dict[str, int] = {}
    for b in buckets:
        totals[b.muscle_group] = totals.get(b.muscle_group, 0) + b.hard_sets

    if not totals:
        await message.answer("Нет hard-сетов за 7 дней.")
        return

    lines = ["Hard-сеты за 7 дней vs ориентиры:"]
    for mg, count in sorted(totals.items()):
        lm = landmarks.get(mg)
        if lm:
            lines.append(f"  {mg}: {count} (MEV {lm.mev} / MAV {lm.mav} / MRV {lm.mrv})")
        else:
            lines.append(f"  {mg}: {count}")
    await message.answer("\n".join(lines))
