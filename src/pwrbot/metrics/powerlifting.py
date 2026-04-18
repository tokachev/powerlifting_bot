"""Powerlifting-specific metrics: Wilks, DOTS, IPF GL, ACWR, rep-max table,
Big 3 summary, lift overview, readiness, meet history, RM-growth YoY.

Pure deterministic functions — no DB, no clock.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from pwrbot.db.repo import WorkoutRow
from pwrbot.db.repo_pl import MeetRow, NextMeetRow, PhaseRow, RecoveryRow, unix_to_date
from pwrbot.metrics.util import iso_week_label
from pwrbot.rules.one_rm import estimate_1rm

LIFT_CANONICAL: dict[str, str] = {
    "squat": "back_squat",
    "bench": "bench_press",
    "deadlift": "deadlift",
}
CANONICAL_TO_LIFT: dict[str, str] = {v: k for k, v in LIFT_CANONICAL.items()}
LIFTS: tuple[str, ...] = ("squat", "bench", "deadlift")
BIG3_CANONICALS: frozenset[str] = frozenset(LIFT_CANONICAL.values())


# ============================================================== Wilks 2020


# Wilks (classic) polynomial coefficients: a0..a5, multiplier 500
_WILKS_M = (
    -216.0475144,
    16.2606339,
    -0.002388645,
    -0.00113732,
    0.00000701863,
    -0.00000000129,
)
_WILKS_F = (
    594.31747775582,
    -27.23842536447,
    0.82112226871,
    -0.00930733913,
    0.00004731582,
    -0.00000009054,
)


def wilks_score(total_kg: float, bodyweight_kg: float, is_female: bool = False) -> float:
    """Classic Wilks coefficient applied to total. Returns 0 for non-positive inputs."""
    if total_kg <= 0 or bodyweight_kg <= 0:
        return 0.0
    c = _WILKS_F if is_female else _WILKS_M
    bw = bodyweight_kg
    denom = (
        c[0]
        + c[1] * bw
        + c[2] * bw**2
        + c[3] * bw**3
        + c[4] * bw**4
        + c[5] * bw**5
    )
    if denom <= 0:
        return 0.0
    return round(total_kg * 500.0 / denom, 2)


# ============================================================== DOTS


_DOTS_M = (-307.75076, 24.0900756, -0.1918759221, 0.0007391293, -0.000001093)
_DOTS_F = (-57.96288, 13.6175032, -0.1126655495, 0.0005158568, -0.0000010706)


def dots_score(total_kg: float, bodyweight_kg: float, is_female: bool = False) -> float:
    if total_kg <= 0 or bodyweight_kg <= 0:
        return 0.0
    c = _DOTS_F if is_female else _DOTS_M
    bw = bodyweight_kg
    denom = (
        c[0] + c[1] * bw + c[2] * bw**2 + c[3] * bw**3 + c[4] * bw**4
    )
    if denom <= 0:
        return 0.0
    return round(total_kg * 500.0 / denom, 2)


# ============================================================== IPF GL


# IPF GL 2020 raw (classic) coefficients
_IPF_GL_RAW_M = (1199.72839, 1025.18162, 0.00921)
_IPF_GL_RAW_F = (610.32796, 1045.59282, 0.03048)


def ipf_gl_points(
    total_kg: float, bodyweight_kg: float, is_female: bool = False
) -> float:
    """IPF GL (Goodlift) points for RAW. Minimum bodyweight clamped at 35kg."""
    if total_kg <= 0 or bodyweight_kg <= 0:
        return 0.0
    a, b, c = _IPF_GL_RAW_F if is_female else _IPF_GL_RAW_M
    bw = max(bodyweight_kg, 35.0)
    import math
    denom = a - b * math.exp(-c * bw)
    if denom <= 0:
        return 0.0
    return round(total_kg * 100.0 / denom, 2)


# ============================================================== Rep Max Table


def rep_max_table(e1rm_kg: float) -> dict[int, float]:
    """Inverse Epley: for each rep count R, compute weight that at R reps gives this 1RM.

    For R=1, weight == e1rm (identity — matches estimate_1rm(w, 1) == w).
    For R>1: weight = e1rm / (1 + R/30).
    """
    if e1rm_kg <= 0:
        return {r: 0.0 for r in (1, 2, 3, 5, 8, 10)}
    out: dict[int, float] = {}
    for r in (1, 2, 3, 5, 8, 10):
        out[r] = round(e1rm_kg, 1) if r == 1 else round(e1rm_kg / (1 + r / 30.0), 1)
    return out


# ============================================================== ACWR


@dataclass(slots=True)
class AcwrResult:
    acute_7d_kg: float
    chronic_28d_avg_kg: float
    ratio: float
    risk_zone: str  # low | sweet | high | danger


def acwr_from_daily_tonnage(tonnage_by_date: dict[date, float], today: date) -> AcwrResult:
    """Acute:Chronic Workload Ratio.

    Acute = sum of last 7 days tonnage.
    Chronic = average of last 28 days in 7-day blocks (= total_28d / 4).
    Sweet spot ~0.8..1.3, high >1.3, danger >1.5.
    """
    acute = sum(
        tonnage_by_date.get(today - timedelta(days=i), 0.0) for i in range(7)
    )
    chronic_total = sum(
        tonnage_by_date.get(today - timedelta(days=i), 0.0) for i in range(28)
    )
    chronic_avg = chronic_total / 4.0
    ratio = acute / chronic_avg if chronic_avg > 0 else 0.0
    if ratio == 0 or ratio < 0.8:
        zone = "low"
    elif ratio <= 1.3:
        zone = "sweet"
    elif ratio <= 1.5:
        zone = "high"
    else:
        zone = "danger"
    return AcwrResult(
        acute_7d_kg=round(acute, 2),
        chronic_28d_avg_kg=round(chronic_avg, 2),
        ratio=round(ratio, 3),
        risk_zone=zone,
    )


# ============================================================== Big 3 summary


@dataclass(slots=True)
class LiftSummary:
    lift: str
    canonical_name: str
    current_e1rm_kg: float
    prev_e1rm_kg: float  # previous window (e.g., one week before)
    delta_pct: float
    pr_kg: float
    target_kg: float
    pct_of_bw: float | None
    sessions_28d: int


def _ts_to_date(ts: int) -> date:
    return datetime.fromtimestamp(ts, tz=UTC).date()


def _best_e1rm_in_window(
    workouts: list[WorkoutRow], canonical: str, since: date, until: date
) -> float:
    best = 0.0
    for w in workouts:
        d = _ts_to_date(w.performed_at)
        if d < since or d > until:
            continue
        for ex in w.exercises:
            if ex.canonical_name != canonical:
                continue
            for s in ex.sets:
                if s.is_warmup or s.reps <= 0 or s.reps > 12:
                    continue
                kg = s.weight_g / 1000.0
                if kg <= 0:
                    continue
                e = estimate_1rm(kg, s.reps)
                if e > best:
                    best = e
    return round(best, 1)


def compute_big3_summary(
    workouts: list[WorkoutRow],
    *,
    today: date,
    bodyweight_kg: float | None,
    pr_by_canonical: dict[str, float],
    next_meet_targets_kg: dict[str, float],
) -> list[LiftSummary]:
    """Compute Big 3 summary for the hero cards on the Dashboard."""
    out: list[LiftSummary] = []
    cur_since = today - timedelta(days=27)
    prev_since = today - timedelta(days=55)
    prev_until = today - timedelta(days=28)
    for lift in LIFTS:
        canonical = LIFT_CANONICAL[lift]
        cur = _best_e1rm_in_window(workouts, canonical, cur_since, today)
        prev = _best_e1rm_in_window(workouts, canonical, prev_since, prev_until)
        delta_pct = 0.0 if prev <= 0 else round((cur - prev) / prev * 100.0, 1)
        pr = pr_by_canonical.get(canonical, cur)
        target = next_meet_targets_kg.get(lift, 0.0)
        pct_bw = None if not bodyweight_kg else round(cur / bodyweight_kg * 100.0, 1)
        sessions = sum(
            1
            for w in workouts
            if cur_since <= _ts_to_date(w.performed_at) <= today
            and any(ex.canonical_name == canonical for ex in w.exercises)
        )
        out.append(
            LiftSummary(
                lift=lift,
                canonical_name=canonical,
                current_e1rm_kg=cur,
                prev_e1rm_kg=prev,
                delta_pct=delta_pct,
                pr_kg=round(pr, 1),
                target_kg=round(target, 1),
                pct_of_bw=pct_bw,
                sessions_28d=sessions,
            )
        )
    return out


# ============================================================== Lift weekly series


@dataclass(slots=True)
class LiftWeek:
    iso_week: str
    e1rm_kg: float
    tonnage_kg: float
    intensity_pct: float | None  # rep-weighted weight as % of 28d rolling 1RM
    avg_velocity_ms: float | None


def compute_lift_weekly(
    workouts: list[WorkoutRow],
    canonical: str,
    *,
    weeks: int,
    today: date,
) -> list[LiftWeek]:
    """Per-ISO-week series for a single lift over the last `weeks` weeks."""
    since = today - timedelta(weeks=weeks)
    # Collect all weeks present + pad to `weeks`
    by_week_reps: dict[str, list[tuple[int, float, float | None]]] = defaultdict(list)
    # reps, weight_kg, velocity_ms
    by_week_best_e1rm: dict[str, float] = defaultdict(float)

    for w in workouts:
        d = _ts_to_date(w.performed_at)
        if d < since or d > today:
            continue
        wlabel = iso_week_label(d)
        for ex in w.exercises:
            if ex.canonical_name != canonical:
                continue
            for s in ex.sets:
                if s.is_warmup or s.reps <= 0:
                    continue
                kg = s.weight_g / 1000.0
                if kg <= 0:
                    continue
                by_week_reps[wlabel].append(
                    (s.reps, kg, getattr(s, "bar_velocity_ms", None))
                )
                if s.reps <= 12:
                    e = estimate_1rm(kg, s.reps)
                    if e > by_week_best_e1rm[wlabel]:
                        by_week_best_e1rm[wlabel] = e

    # Rolling 28d best e1rm per day for intensity% computation
    # Simplification: use max e1rm in the current week as the denominator
    labels = sorted(set(by_week_reps.keys()) | set(by_week_best_e1rm.keys()))
    result: list[LiftWeek] = []
    running_best_e1rm = 0.0
    for label in labels:
        running_best_e1rm = max(running_best_e1rm, by_week_best_e1rm.get(label, 0.0))
        sets = by_week_reps.get(label, [])
        tonnage = sum(r * kg for r, kg, _ in sets)
        rep_w = sum(r * kg for r, kg, _ in sets)
        total_reps = sum(r for r, _, _ in sets)
        avg_weight = rep_w / total_reps if total_reps else 0.0
        intensity_pct = (
            round(avg_weight / running_best_e1rm * 100.0, 1)
            if running_best_e1rm > 0
            else None
        )
        vel_points = [v for _, _, v in sets if v is not None]
        avg_vel = (
            round(sum(vel_points) / len(vel_points), 3) if vel_points else None
        )
        result.append(
            LiftWeek(
                iso_week=label,
                e1rm_kg=round(by_week_best_e1rm.get(label, 0.0), 1),
                tonnage_kg=round(tonnage, 1),
                intensity_pct=intensity_pct,
                avg_velocity_ms=avg_vel,
            )
        )
    return result


# ============================================================== Recent sessions


@dataclass(slots=True)
class RecentSession:
    date: date
    focus: str  # 'squat' | 'bench' | 'deadlift' | 'accessory'
    top_set_kg: float
    top_set_reps: int
    total_volume_kg: float
    avg_rpe: float | None
    duration_min: int | None


def compute_recent_sessions(
    workouts: list[WorkoutRow], *, limit: int = 7
) -> list[RecentSession]:
    """Last `limit` workouts, reverse chronological."""
    sorted_w = sorted(workouts, key=lambda w: w.performed_at, reverse=True)[:limit]
    out: list[RecentSession] = []
    for w in sorted_w:
        d = _ts_to_date(w.performed_at)
        per_lift_reps: dict[str, int] = defaultdict(int)
        top_weight = 0.0
        top_reps = 0
        total_vol = 0.0
        rpe_vals: list[float] = []
        for ex in w.exercises:
            lift = CANONICAL_TO_LIFT.get(ex.canonical_name or "", "accessory")
            for s in ex.sets:
                if s.is_warmup or s.reps <= 0:
                    continue
                kg = s.weight_g / 1000.0
                total_vol += s.reps * kg
                per_lift_reps[lift] += s.reps
                if kg > top_weight:
                    top_weight = kg
                    top_reps = s.reps
                if s.rpe is not None:
                    rpe_vals.append(s.rpe)
        focus = max(per_lift_reps.items(), key=lambda kv: kv[1])[0] if per_lift_reps else "accessory"
        out.append(
            RecentSession(
                date=d,
                focus=focus,
                top_set_kg=round(top_weight, 1),
                top_set_reps=top_reps,
                total_volume_kg=round(total_vol, 1),
                avg_rpe=round(sum(rpe_vals) / len(rpe_vals), 1) if rpe_vals else None,
                duration_min=None,  # not tracked in schema
            )
        )
    return out


# ============================================================== Accessories overview


@dataclass(slots=True)
class AccessoryOverview:
    canonical_name: str
    e1rm_kg: float
    delta_kg: float  # vs previous equal window
    sets_28d: int
    top_set_kg: float


def compute_accessories_overview(
    workouts: list[WorkoutRow],
    *,
    today: date,
    big3_canonicals: frozenset[str] = BIG3_CANONICALS,
    limit: int = 8,
) -> list[AccessoryOverview]:
    """Non-Big3 exercises, ranked by current e1RM, with delta vs. prior 28 days."""
    cur_since = today - timedelta(days=27)
    prev_since = today - timedelta(days=55)
    prev_until = today - timedelta(days=28)

    cur_best: dict[str, tuple[float, float, int]] = {}  # e1rm, top_weight, sets_count
    prev_best: dict[str, float] = {}

    for w in workouts:
        d = _ts_to_date(w.performed_at)
        for ex in w.exercises:
            if not ex.canonical_name or ex.canonical_name in big3_canonicals:
                continue
            for s in ex.sets:
                if s.is_warmup or s.reps <= 0 or s.reps > 12:
                    continue
                kg = s.weight_g / 1000.0
                if kg <= 0:
                    continue
                e = estimate_1rm(kg, s.reps)
                if cur_since <= d <= today:
                    ex_e1rm, top_w, sets_n = cur_best.get(ex.canonical_name, (0.0, 0.0, 0))
                    new_e1rm = max(ex_e1rm, e)
                    new_top = max(top_w, kg)
                    cur_best[ex.canonical_name] = (new_e1rm, new_top, sets_n + 1)
                elif prev_since <= d <= prev_until:
                    prev_best[ex.canonical_name] = max(
                        prev_best.get(ex.canonical_name, 0.0), e
                    )

    ranked = sorted(cur_best.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
    out = [
        AccessoryOverview(
            canonical_name=name,
            e1rm_kg=round(e, 1),
            delta_kg=round(e - prev_best.get(name, 0.0), 1) if prev_best.get(name) else 0.0,
            sets_28d=sets_n,
            top_set_kg=round(top_w, 1),
        )
        for name, (e, top_w, sets_n) in ranked
    ]
    return out


# ============================================================== Readiness / sleep


@dataclass(slots=True)
class ReadinessPoint:
    date: date
    sleep_hours: float | None
    hrv_ms: float | None
    rhr_bpm: int | None
    recovery_pct: int | None


@dataclass(slots=True)
class ReadinessSummary:
    points: list[ReadinessPoint]
    avg_sleep_hours: float | None
    avg_hrv_ms: float | None
    avg_rhr_bpm: float | None
    latest_recovery_pct: int | None


def compute_readiness(rows: list[RecoveryRow]) -> ReadinessSummary:
    points = [
        ReadinessPoint(
            date=unix_to_date(r.recorded_date),
            sleep_hours=r.sleep_hours,
            hrv_ms=r.hrv_ms,
            rhr_bpm=r.rhr_bpm,
            recovery_pct=r.recovery_pct,
        )
        for r in rows
    ]
    sleeps = [p.sleep_hours for p in points if p.sleep_hours is not None]
    hrvs = [p.hrv_ms for p in points if p.hrv_ms is not None]
    rhrs = [p.rhr_bpm for p in points if p.rhr_bpm is not None]
    latest_rec = points[-1].recovery_pct if points else None
    return ReadinessSummary(
        points=points,
        avg_sleep_hours=round(sum(sleeps) / len(sleeps), 2) if sleeps else None,
        avg_hrv_ms=round(sum(hrvs) / len(hrvs), 1) if hrvs else None,
        avg_rhr_bpm=round(sum(rhrs) / len(rhrs), 1) if rhrs else None,
        latest_recovery_pct=latest_rec,
    )


# ============================================================== Calendar 16w heatmap


def compute_calendar_heatmap_16w(
    workouts: list[WorkoutRow], *, today: date
) -> list[tuple[date, int]]:
    """Return one (date, intensity_0_to_4) per day for last 112 days (16 weeks).

    Intensity bucket based on daily working-set count:
      0: no workout
      1: 1-9 sets
      2: 10-14
      3: 15-19
      4: 20+
    """
    since = today - timedelta(days=111)
    by_date: dict[date, int] = defaultdict(int)
    for w in workouts:
        d = _ts_to_date(w.performed_at)
        if d < since or d > today:
            continue
        for ex in w.exercises:
            for s in ex.sets:
                if s.is_warmup or s.reps <= 0:
                    continue
                by_date[d] += 1

    def bucket(n: int) -> int:
        if n == 0:
            return 0
        if n < 10:
            return 1
        if n < 15:
            return 2
        if n < 20:
            return 3
        return 4

    out: list[tuple[date, int]] = []
    for i in range(112):
        d = since + timedelta(days=i)
        out.append((d, bucket(by_date.get(d, 0))))
    return out


# ============================================================== Meet history


@dataclass(slots=True)
class MeetHistoryEntry:
    id: int
    date: date
    name: str
    category: str | None
    federation: str | None
    bodyweight_kg: float | None
    squat_kg: float
    bench_kg: float
    deadlift_kg: float
    total_kg: float
    wilks: float | None
    dots: float | None
    ipf_gl: float | None
    place: int | None
    is_gym_meet: bool


@dataclass(slots=True)
class MeetHistorySummary:
    meets: list[MeetHistoryEntry]
    total_meets: int
    best_total_kg: float
    best_total_at: date | None
    best_gym_total_kg: float
    best_wilks: float | None
    best_dots: float | None
    podiums: int


def compute_meet_history(meets: list[MeetRow]) -> MeetHistorySummary:
    entries = [
        MeetHistoryEntry(
            id=m.id,
            date=unix_to_date(m.meet_date),
            name=m.name,
            category=m.category,
            federation=m.federation,
            bodyweight_kg=m.bodyweight_g / 1000.0 if m.bodyweight_g else None,
            squat_kg=m.squat_g / 1000.0,
            bench_kg=m.bench_g / 1000.0,
            deadlift_kg=m.deadlift_g / 1000.0,
            total_kg=m.total_g / 1000.0,
            wilks=m.wilks,
            dots=m.dots,
            ipf_gl=m.ipf_gl,
            place=m.place,
            is_gym_meet=m.is_gym_meet,
        )
        for m in meets
    ]
    official = [e for e in entries if not e.is_gym_meet]
    gym = [e for e in entries if e.is_gym_meet]
    best = max(official, key=lambda e: e.total_kg, default=None)
    best_gym = max(gym, key=lambda e: e.total_kg, default=None)
    wilks_vals = [e.wilks for e in entries if e.wilks is not None]
    dots_vals = [e.dots for e in entries if e.dots is not None]
    podiums = sum(1 for e in official if e.place is not None and e.place <= 3)
    return MeetHistorySummary(
        meets=entries,
        total_meets=len(official),
        best_total_kg=best.total_kg if best else 0.0,
        best_total_at=best.date if best else None,
        best_gym_total_kg=best_gym.total_kg if best_gym else 0.0,
        best_wilks=max(wilks_vals) if wilks_vals else None,
        best_dots=max(dots_vals) if dots_vals else None,
        podiums=podiums,
    )


# ============================================================== 1RM growth YoY


@dataclass(slots=True)
class RmGrowth:
    lift: str
    start_kg: float
    end_kg: float
    delta_kg: float
    delta_pct: float


def compute_rm_growth_yoy(
    workouts: list[WorkoutRow], *, today: date
) -> list[RmGrowth]:
    """Compare best e1RM in [today-365d .. today-183d] vs [today-182d..today] for Big 3."""
    window_start = today - timedelta(days=365)
    mid = today - timedelta(days=183)
    out: list[RmGrowth] = []
    for lift in LIFTS:
        canonical = LIFT_CANONICAL[lift]
        start = _best_e1rm_in_window(workouts, canonical, window_start, mid)
        end = _best_e1rm_in_window(workouts, canonical, mid, today)
        delta = round(end - start, 1)
        pct = round((delta / start * 100.0), 1) if start > 0 else 0.0
        out.append(RmGrowth(lift=lift, start_kg=start, end_kg=end, delta_kg=delta, delta_pct=pct))
    return out


# ============================================================== Set recommendations


@dataclass(slots=True)
class SetRecommendation:
    name: str  # Volume | Strength | Peaking
    scheme: str  # "5×5"
    intensity_pct: int
    weight_kg: float


def compute_set_recommendations(e1rm_kg: float) -> list[SetRecommendation]:
    """Volume 5x5 @72%, Strength 5x3 @82%, Peaking 3x1 @92% of e1RM."""
    recs = [
        ("Volume", "5×5", 72),
        ("Strength", "5×3", 82),
        ("Peaking", "3×1", 92),
    ]
    return [
        SetRecommendation(
            name=name,
            scheme=scheme,
            intensity_pct=pct,
            weight_kg=round(e1rm_kg * pct / 100.0, 1),
        )
        for name, scheme, pct in recs
    ]


# ============================================================== Phase helpers


def phases_to_week_map(
    phases: list[PhaseRow], *, weeks: int, today: date
) -> dict[str, str]:
    """Return {iso_week_label -> phase_name} for the last `weeks` weeks.

    Weeks not covered by any phase map to 'unscheduled'.
    """
    result: dict[str, str] = {}
    for i in range(weeks):
        d = today - timedelta(weeks=weeks - 1 - i)
        label = iso_week_label(d)
        matched = next(
            (p for p in phases if p.start_date <= int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp()) <= p.end_date),
            None,
        )
        result[label] = matched.phase_name if matched else "unscheduled"
    return result


# ============================================================== Daily tonnage helper


def daily_tonnage(workouts: list[WorkoutRow]) -> dict[date, float]:
    by_date: dict[date, float] = defaultdict(float)
    for w in workouts:
        d = _ts_to_date(w.performed_at)
        for ex in w.exercises:
            for s in ex.sets:
                if s.is_warmup or s.reps <= 0:
                    continue
                by_date[d] += s.reps * (s.weight_g / 1000.0)
    return dict(by_date)


# ============================================================== Next meet echo


@dataclass(slots=True)
class NextMeetEcho:
    meet_date: date
    days_left: int
    name: str
    category: str | None
    federation: str | None
    target_squat_kg: float
    target_bench_kg: float
    target_deadlift_kg: float
    target_total_kg: float
    attempts_kg: dict[str, list[float]]


def next_meet_to_echo(
    row: NextMeetRow | None, *, today: date
) -> NextMeetEcho | None:
    if row is None:
        return None
    md = unix_to_date(row.meet_date)
    days_left = (md - today).days
    return NextMeetEcho(
        meet_date=md,
        days_left=days_left,
        name=row.name,
        category=row.category,
        federation=row.federation,
        target_squat_kg=row.target_squat_g / 1000.0,
        target_bench_kg=row.target_bench_g / 1000.0,
        target_deadlift_kg=row.target_deadlift_g / 1000.0,
        target_total_kg=(row.target_squat_g + row.target_bench_g + row.target_deadlift_g) / 1000.0,
        attempts_kg={
            lift: [g / 1000.0 for g in row.attempts.get(lift, [])]
            for lift in ("squat", "bench", "deadlift")
        },
    )
