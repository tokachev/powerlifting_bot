"""Format helpers for bot replies. No LLM here — pure string assembly."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from pwrbot.db.repo import WorkoutRow
from pwrbot.domain.models import WorkoutPayload
from pwrbot.metrics.pr import DetectedPR
from pwrbot.rules.one_rm import OneRMEstimate
from pwrbot.services.analyze import AnalyzeResult

_BIG3_DISPLAY: dict[str, str] = {
    "back_squat": "присед",
    "front_squat": "фронт присед",
    "bench_press": "жим лёжа",
    "incline_bench_press": "наклонный жим",
    "deadlift": "становая",
    "sumo_deadlift": "становая сумо",
}
_TELEGRAM_MESSAGE_LIMIT = 4096
_EXPLANATION_LIMIT = 1500
_PATTERN_DISPLAY: dict[str, str] = {
    "accessory": "вспомогательные",
    "hinge": "становая/наклоны",
    "pull": "тяги на спину",
    "push": "жимы",
    "squat": "приседания",
}
_EXPLANATION_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bpush\s*/\s*pull\b", re.IGNORECASE), "жимы/тяги на спину"),
    (re.compile(r"\bsquat\s*/\s*hinge\b", re.IGNORECASE), "приседания/становая и наклоны"),
    (re.compile(r"\bhard[-_ ]sets?\b", re.IGNORECASE), "тяжёлые сеты"),
    (re.compile(r"\bhard[-_ ]сетов\b", re.IGNORECASE), "тяжёлых сетов"),
    (re.compile(r"\bhard[-_ ]сета\b", re.IGNORECASE), "тяжёлых сета"),
    (re.compile(r"\bwindow\b", re.IGNORECASE), "выбранном окне"),
    (re.compile(r"\bpattern\b", re.IGNORECASE), "типе движения"),
    (re.compile(r"\bratio\b", re.IGNORECASE), "соотношение"),
    (re.compile(r"\btarget\b", re.IGNORECASE), "цель"),
    (re.compile(r"\bvolume\b", re.IGNORECASE), "объём"),
    (re.compile(r"\bfocus\b", re.IGNORECASE), "акцент"),
    (re.compile(r"\bvs\b", re.IGNORECASE), "против"),
    (re.compile(r"\bin\b", re.IGNORECASE), "в"),
    (re.compile(r"\baccessory\b", re.IGNORECASE), "вспомогательные упражнения"),
    (re.compile(r"\bhinge\b", re.IGNORECASE), "становая/наклоны"),
    (re.compile(r"\bpull\b", re.IGNORECASE), "тяги на спину"),
    (re.compile(r"\bpush\b", re.IGNORECASE), "жимы"),
    (re.compile(r"\bsquat\b", re.IGNORECASE), "приседания"),
)


def _fmt_weight(kg: float) -> str:
    if kg == int(kg):
        return f"{int(kg)}"
    return f"{kg:.1f}"


def _fmt_pattern(pattern: str | None) -> str:
    if pattern is None:
        return "?"
    return _PATTERN_DISPLAY.get(pattern, pattern)


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
                f"дисбаланс жимы/тяги на спину по 28д: {ratio_str} "
                f"(жимы {f.get('push_hard_sets')} / тяги {f.get('pull_hard_sets')})"
            )
        if axis == "squat_hinge":
            return (
                f"дисбаланс приседания/становая и наклоны по 28д: {ratio_str} "
                f"(приседания {f.get('squat_hard_sets')} / "
                f"становая и наклоны {f.get('hinge_hard_sets')})"
            )
    if kind == "recovery_risk":
        if f.get("subtype") == "tonnage_spike":
            return (
                f"всплеск тоннажа: {f.get('ratio')}× "
                f"({f.get('previous_tonnage_kg')} → {f.get('current_tonnage_kg')} кг)"
            )
        return (
            f"перегрузка {_fmt_pattern(f.get('pattern'))}: "
            f"{f.get('hard_sets_7d')} тяжёлых сетов за 7 дней (лимит {f.get('cap')})"
        )
    return str(f)


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _russify_explanation(text: str) -> str:
    for pattern, replacement in _EXPLANATION_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def _format_explain_backend(name: str, result) -> str:
    if result.text:
        text = _russify_explanation(result.text.strip())
        text = _truncate_text(text, _EXPLANATION_LIMIT)
        if result.latency_s is not None:
            return f"{name} ({result.latency_s:.1f}s):\n{text}"
        return f"{name}:\n{text}"
    if name == "Codex" and result.error == "disabled":
        return "Codex: отключён"
    if result.error:
        return f"{name}: ошибка ({_truncate_text(result.error, 300)})"
    return f"{name}: нет объяснения"


def format_analysis(result: AnalyzeResult) -> str:
    lines = [f"Анализ за {result.window_days} дней:"]
    window = result.metrics.get("window", {})
    tonnage = window.get("total_tonnage_kg", 0)
    hard_sets = window.get("total_hard_sets", 0)
    lines.append(f"  тоннаж: {_fmt_weight(tonnage)} кг, тяжёлых сетов: {hard_sets}")
    hard_by_p = window.get("hard_sets_by_pattern", {})
    if hard_by_p:
        parts = ", ".join(
            f"{_fmt_pattern(k)}: {v}" for k, v in sorted(hard_by_p.items())
        )
        lines.append(f"  по типам движений: {parts}")

    if result.flags:
        lines.append("Флаги:")
        for f in result.flags:
            lines.append(f"  ⚠ {format_flag(f)}")
    else:
        lines.append("Флагов нет.")

    explanations = [
        _format_explain_backend("Gemma", result.explanation_gemma),
        _format_explain_backend("Codex", result.explanation_codex),
    ]
    if explanations:
        lines.append("")
        lines.append("\n\n".join(explanations))
    text = "\n".join(lines)
    return _truncate_text(text, _TELEGRAM_MESSAGE_LIMIT)


def format_rm_estimates(
    estimates: list[OneRMEstimate],
    body_weight_kg: float | None = None,
) -> str | None:
    """Format 1RM estimates block. Returns None if the list is empty."""
    if not estimates:
        return None
    lines = ["Расчётный 1RM:"]
    for e in estimates:
        name = _BIG3_DISPLAY.get(e.canonical_name, e.canonical_name)
        bw_str = ""
        if body_weight_kg and body_weight_kg > 0:
            ratio = e.estimated_1rm_kg / body_weight_kg
            bw_str = f" / ~{ratio:.2f} BW"
        lines.append(
            f"  {name}: ~{_fmt_weight(e.estimated_1rm_kg)} кг{bw_str} "
            f"(на основе {_fmt_weight(e.best_set_weight_kg)}×{e.best_set_reps})"
        )
    return "\n".join(lines)


def format_new_prs(prs: list[DetectedPR]) -> str | None:
    """Format PR notifications. Returns None if empty."""
    if not prs:
        return None
    lines = []
    for pr in prs:
        name = _BIG3_DISPLAY.get(pr.canonical_name, pr.canonical_name)
        delta = ""
        if pr.previous_1rm_kg is not None:
            diff = pr.estimated_1rm_kg - pr.previous_1rm_kg
            delta = f" (было ~{_fmt_weight(pr.previous_1rm_kg)} кг, +{_fmt_weight(diff)})"
        lines.append(
            f"  {name}: e1RM ~{_fmt_weight(pr.estimated_1rm_kg)} кг{delta}"
        )
    header = "Новый рекорд!" if len(prs) == 1 else "Новые рекорды!"
    return header + "\n" + "\n".join(lines)


def format_ingest_reply(
    parsed: WorkoutPayload,
    analysis: AnalyzeResult | None,
    rm_estimates: list[OneRMEstimate] | None = None,
    body_weight_kg: float | None = None,
    new_prs: list[DetectedPR] | None = None,
) -> str:
    parts = [format_parsed_workout(parsed)]
    pr_text = format_new_prs(new_prs or [])
    if pr_text:
        parts.append("")
        parts.append(pr_text)
    rm_text = format_rm_estimates(rm_estimates or [], body_weight_kg=body_weight_kg)
    if rm_text:
        parts.append("")
        parts.append(rm_text)
    if analysis is not None:
        parts.append("")
        parts.append(format_analysis(analysis))
    return "\n".join(parts)
