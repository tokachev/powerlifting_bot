"""Format helpers for bot replies. No LLM here — pure string assembly."""

from __future__ import annotations

from datetime import UTC, datetime

from pwrbot.db.repo import WorkoutRow
from pwrbot.domain.models import WorkoutPayload
from pwrbot.services.analyze import AnalyzeResult


def _fmt_weight(kg: float) -> str:
    if kg == int(kg):
        return f"{int(kg)}"
    return f"{kg:.1f}"


def _fmt_set(reps: int, weight_kg: float, rpe: float | None, is_warmup: bool) -> str:
    """Format a single set. Sets with weight==0 (bodyweight/machine without weight
    column) are rendered as `{reps}` instead of `{reps}×0кг`."""
    marker = " (разминка)" if is_warmup else ""
    rpe_str = f" @{_fmt_weight(rpe)}" if rpe is not None else ""
    if weight_kg == 0:
        return f"{reps}{rpe_str}{marker}"
    return f"{reps}×{_fmt_weight(weight_kg)}кг{rpe_str}{marker}"


def format_parsed_workout(payload: WorkoutPayload) -> str:
    lines = ["Записал:"]
    for ex in payload.exercises:
        name = ex.canonical_name or ex.raw_name
        set_strs = [
            _fmt_set(s.reps, s.weight_kg, s.rpe, s.is_warmup) for s in ex.sets
        ]
        lines.append(f"• {name}: " + ", ".join(set_strs))
    return "\n".join(lines)


def format_workout_row(w: WorkoutRow) -> str:
    ts = datetime.fromtimestamp(w.performed_at, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"Тренировка {ts}:"]
    for ex in w.exercises:
        name = ex.canonical_name or ex.raw_name
        set_strs = [
            _fmt_set(s.reps, s.weight_g / 1000.0, s.rpe, s.is_warmup) for s in ex.sets
        ]
        lines.append(f"• {name}: " + ", ".join(set_strs))
    return "\n".join(lines)


def format_week_summary(workouts: list[WorkoutRow]) -> str:
    if not workouts:
        return "За последние 7 дней тренировок нет."
    lines = [f"За 7 дней: {len(workouts)} тренировок"]
    for w in sorted(workouts, key=lambda x: x.performed_at):
        ts = datetime.fromtimestamp(w.performed_at, tz=UTC).strftime("%m-%d")
        total_sets = sum(len(ex.sets) for ex in w.exercises)
        names = ", ".join((ex.canonical_name or ex.raw_name) for ex in w.exercises[:3])
        if len(w.exercises) > 3:
            names += " …"
        lines.append(f"• {ts}: {total_sets} сетов — {names}")
    return "\n".join(lines)


def format_flag(f: dict) -> str:
    kind = f.get("kind")
    if kind == "imbalance":
        axis = f.get("axis", "?")
        ratio = f.get("ratio")
        ratio_str = "∞" if ratio == float("inf") or ratio is None else f"{ratio:.2f}"
        if axis == "push_pull":
            return (
                f"дисбаланс push/pull: {ratio_str} "
                f"(push {f.get('push_hard_sets')} / pull {f.get('pull_hard_sets')})"
            )
        if axis == "squat_hinge":
            return (
                f"дисбаланс squat/hinge: {ratio_str} "
                f"(squat {f.get('squat_hard_sets')} / hinge {f.get('hinge_hard_sets')})"
            )
    if kind == "recovery_risk":
        if f.get("subtype") == "tonnage_spike":
            return (
                f"всплеск тоннажа: {f.get('ratio')}× "
                f"({f.get('previous_tonnage_kg')} → {f.get('current_tonnage_kg')} кг)"
            )
        return (
            f"перегрузка {f.get('pattern')}: "
            f"{f.get('hard_sets_7d')} hard-сетов за 7д (лимит {f.get('cap')})"
        )
    return str(f)


def format_analysis(result: AnalyzeResult) -> str:
    lines = [f"Анализ за {result.window_days} дней:"]
    window = result.metrics.get("window", {})
    tonnage = window.get("total_tonnage_kg", 0)
    hard_sets = window.get("total_hard_sets", 0)
    lines.append(f"  тоннаж: {_fmt_weight(tonnage)} кг, hard-сетов: {hard_sets}")
    hard_by_p = window.get("hard_sets_by_pattern", {})
    if hard_by_p:
        parts = ", ".join(f"{k}: {v}" for k, v in sorted(hard_by_p.items()))
        lines.append(f"  по паттернам: {parts}")

    if result.flags:
        lines.append("Флаги:")
        for f in result.flags:
            lines.append(f"  ⚠ {format_flag(f)}")
    else:
        lines.append("Флагов нет.")

    if result.explanation:
        lines.append("")
        lines.append(result.explanation)
    return "\n".join(lines)


def format_ingest_reply(parsed: WorkoutPayload, analysis: AnalyzeResult | None) -> str:
    parts = [format_parsed_workout(parsed)]
    if analysis is not None:
        parts.append("")
        parts.append(format_analysis(analysis))
    return "\n".join(parts)
