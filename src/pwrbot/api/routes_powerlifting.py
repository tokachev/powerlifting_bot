"""Powerlifting API endpoints: overview, lift-detail, history, config, write."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, HTTPException, Query, Request

from pwrbot.api.pl_schemas import (
    AccessoryItem,
    AcwrSchema,
    Big3LiftCard,
    BodyweightCreate,
    BodyweightPoint,
    CalendarCell,
    HistoryKpiSchema,
    HistoryResponse,
    KpiStripData,
    LiftDetailResponse,
    LiftWeekPoint,
    MeetCreate,
    MeetEntrySchema,
    NextMeetEchoSchema,
    NextMeetUpdate,
    NiggleCreate,
    NiggleItem,
    OverviewResponse,
    PersonalRecordCard,
    PhaseSchema,
    PRItemSchema,
    ReadinessDayPoint,
    ReadinessSummary,
    RecentSessionItem,
    RecoveryCreate,
    RepMaxEntry,
    RmGrowthItem,
    SetRecommendationItem,
    TechniqueNoteItem,
)
from pwrbot.db import repo, repo_pl
from pwrbot.domain.catalog import Catalog
from pwrbot.metrics.powerlifting import (
    CANONICAL_TO_LIFT,
    LIFT_CANONICAL,
    LIFTS,
    acwr_from_daily_tonnage,
    best_weight_by_min_reps,
    compute_accessories_overview,
    compute_big3_summary,
    compute_calendar_heatmap_16w,
    compute_lift_weekly,
    compute_meet_history,
    compute_readiness,
    compute_recent_sessions,
    compute_rm_growth_yoy,
    compute_set_recommendations,
    daily_tonnage,
    dots_score,
    ipf_gl_points,
    next_meet_to_echo,
    phases_to_week_map,
    rep_max_table,
    wilks_score,
)

router = APIRouter(prefix="/api/pl", tags=["powerlifting"])


def _date_to_unix_start(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


def _date_to_unix_end(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC).timestamp())


async def _ensure_user(conn: aiosqlite.Connection, user_id: int) -> None:
    async with conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)) as cur:
        if (await cur.fetchone()) is None:
            raise HTTPException(status_code=404, detail="user not found")


async def _pr_by_lift(
    conn: aiosqlite.Connection, *, user_id: int, catalog: Catalog
) -> dict[str, float]:
    """Best e1RM PR per Big 3 lift, aggregated across all variants sharing
    the same ``target_group`` and scaled by each variant's coefficient.
    """
    out: dict[str, float] = {}
    for entry in catalog.entries:
        if entry.target_group is None:
            continue
        g = await repo.get_best_e1rm_for_exercise(
            conn, user_id=user_id, canonical_name=entry.canonical_name
        )
        if g is None:
            continue
        kg = g / 1000.0
        coef = entry.main_lift_coefficient or 1.0
        scaled = kg / coef if coef > 0 else kg
        if scaled > out.get(entry.target_group, 0.0):
            out[entry.target_group] = scaled
    return out


# ========================================================= GET /api/pl/overview


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    request: Request,
    user_id: Annotated[int, Query(...)],
    weeks: Annotated[int, Query(ge=4, le=52)] = 14,
    is_female: Annotated[bool, Query()] = False,
) -> OverviewResponse:
    c: aiosqlite.Connection = request.app.state.conn
    cat: Catalog = request.app.state.catalog
    await _ensure_user(c, user_id)

    today = datetime.now(UTC).date()
    since_d = today - timedelta(weeks=weeks)
    since_ts = _date_to_unix_start(since_d)
    until_ts = _date_to_unix_end(today)

    workouts = await repo.get_workouts_in_window(
        c, user_id=user_id, since_ts=since_ts, until_ts=until_ts
    )
    meets_rows = await repo_pl.list_meets(c, user_id=user_id)
    next_meet_row = await repo_pl.get_next_meet(c, user_id=user_id)
    recovery_rows = await repo_pl.list_recovery(
        c, user_id=user_id, since_ts=_date_to_unix_start(today - timedelta(days=27)),
        until_ts=until_ts,
    )
    niggles_rows = await repo_pl.list_niggles(c, user_id=user_id, active_only=True)
    phases = await repo_pl.list_phases(c, user_id=user_id, since_ts=since_ts, until_ts=until_ts)
    bw_rows = await repo.get_body_weight_history(
        c, user_id=user_id, since_ts=since_ts, until_ts=until_ts
    )

    pr_by_lift = await _pr_by_lift(c, user_id=user_id, catalog=cat)

    latest_bw_kg: float | None = None
    if bw_rows:
        latest_bw_kg = bw_rows[-1][1] / 1000.0

    # Targets from next_meet_config
    targets_kg: dict[str, float] = {"squat": 0.0, "bench": 0.0, "deadlift": 0.0}
    if next_meet_row:
        targets_kg = {
            "squat": next_meet_row.target_squat_g / 1000.0,
            "bench": next_meet_row.target_bench_g / 1000.0,
            "deadlift": next_meet_row.target_deadlift_g / 1000.0,
        }

    big3 = compute_big3_summary(
        workouts,
        today=today,
        bodyweight_kg=latest_bw_kg,
        pr_by_lift=pr_by_lift,
        next_meet_targets_kg=targets_kg,
        catalog=cat,
    )

    # KPI: total Big3 e1RM + Wilks/DOTS if bodyweight known
    total_e1rm = sum(b.current_e1rm_kg for b in big3)
    wilks_v = (
        wilks_score(total_e1rm, latest_bw_kg, is_female) if latest_bw_kg else None
    )
    dots_v = dots_score(total_e1rm, latest_bw_kg, is_female) if latest_bw_kg else None
    nm_echo = next_meet_to_echo(next_meet_row, today=today)

    kpi = KpiStripData(
        total_kg=round(total_e1rm, 1),
        wilks=wilks_v,
        dots=dots_v,
        bodyweight_kg=latest_bw_kg,
        next_meet_days_left=nm_echo.days_left if nm_echo else None,
    )

    # Per-lift weekly series for tonnage + intensity
    phase_map = phases_to_week_map(phases, weeks=weeks, today=today)
    tonnage_by_lift: dict[str, list[LiftWeekPoint]] = {}
    intensity_by_lift: dict[str, list[LiftWeekPoint]] = {}
    for lift in LIFTS:
        series = compute_lift_weekly(
            workouts, target_group=lift, catalog=cat, weeks=weeks, today=today
        )
        points = [
            LiftWeekPoint(
                iso_week=p.iso_week,
                e1rm_kg=p.e1rm_kg,
                tonnage_kg=p.tonnage_kg,
                intensity_pct=p.intensity_pct,
                avg_velocity_ms=p.avg_velocity_ms,
                phase=phase_map.get(p.iso_week, "unscheduled"),
            )
            for p in series
        ]
        tonnage_by_lift[lift] = points
        intensity_by_lift[lift] = points

    calendar_raw = compute_calendar_heatmap_16w(workouts, today=today)
    calendar = [CalendarCell(date=d, intensity=v) for d, v in calendar_raw]

    readiness_s = compute_readiness(recovery_rows)
    readiness = ReadinessSummary(
        points=[
            ReadinessDayPoint(
                date=p.date,
                sleep_hours=p.sleep_hours,
                hrv_ms=p.hrv_ms,
                rhr_bpm=p.rhr_bpm,
                recovery_pct=p.recovery_pct,
            )
            for p in readiness_s.points
        ],
        avg_sleep_hours=readiness_s.avg_sleep_hours,
        avg_hrv_ms=readiness_s.avg_hrv_ms,
        avg_rhr_bpm=readiness_s.avg_rhr_bpm,
        latest_recovery_pct=readiness_s.latest_recovery_pct,
    )

    accessories_raw = compute_accessories_overview(workouts, today=today, catalog=cat)
    accessories = [
        AccessoryItem(
            canonical_name=a.canonical_name,
            e1rm_kg=a.e1rm_kg,
            delta_kg=a.delta_kg,
            sets_28d=a.sets_28d,
            top_set_kg=a.top_set_kg,
        )
        for a in accessories_raw
    ]

    niggles = [
        NiggleItem(
            id=n.id,
            recorded_date=repo_pl.unix_to_date(n.recorded_date),
            body_area=n.body_area,
            severity=n.severity,
            note=n.note,
        )
        for n in niggles_rows
    ]

    bw_trend = [
        BodyweightPoint(date=repo_pl.unix_to_date(ts), weight_kg=g / 1000.0)
        for ts, g in bw_rows
    ]

    recent_raw = compute_recent_sessions(workouts, limit=7, catalog=cat)
    recent = [
        RecentSessionItem(
            date=s.date,
            focus=s.focus,
            top_set_kg=s.top_set_kg,
            top_set_reps=s.top_set_reps,
            total_volume_kg=s.total_volume_kg,
            avg_rpe=s.avg_rpe,
            duration_min=s.duration_min,
        )
        for s in recent_raw
    ]

    phase_schemas = [
        PhaseSchema(
            phase_name=p.phase_name,
            start_date=repo_pl.unix_to_date(p.start_date),
            end_date=repo_pl.unix_to_date(p.end_date),
            color_hex=p.color_hex,
        )
        for p in phases
    ]

    nm_schema = (
        NextMeetEchoSchema(
            meet_date=nm_echo.meet_date,
            days_left=nm_echo.days_left,
            name=nm_echo.name,
            category=nm_echo.category,
            federation=nm_echo.federation,
            target_squat_kg=nm_echo.target_squat_kg,
            target_bench_kg=nm_echo.target_bench_kg,
            target_deadlift_kg=nm_echo.target_deadlift_kg,
            target_total_kg=nm_echo.target_total_kg,
            attempts_kg=nm_echo.attempts_kg,
        )
        if nm_echo
        else None
    )

    # consume meets_rows to compute wilks/dots fallback if needed (not used here)
    del meets_rows

    return OverviewResponse(
        kpi=kpi,
        big3=[
            Big3LiftCard(
                lift=b.lift,
                canonical_name=b.canonical_name,
                current_e1rm_kg=b.current_e1rm_kg,
                prev_e1rm_kg=b.prev_e1rm_kg,
                delta_pct=b.delta_pct,
                pr_kg=b.pr_kg,
                target_kg=b.target_kg,
                pct_of_bw=b.pct_of_bw,
                sessions_28d=b.sessions_28d,
            )
            for b in big3
        ],
        tonnage_by_lift=tonnage_by_lift,
        intensity_by_lift=intensity_by_lift,
        calendar=calendar,
        readiness=readiness,
        next_meet=nm_schema,
        accessories=accessories,
        niggles=niggles,
        bodyweight_trend=bw_trend,
        recent_sessions=recent,
        phases=phase_schemas,
    )


# ========================================================= GET /api/pl/lift/{lift}


@router.get("/lift/{lift}", response_model=LiftDetailResponse)
async def lift_detail(
    request: Request,
    lift: str,
    user_id: Annotated[int, Query(...)],
    weeks: Annotated[int, Query(ge=4, le=52)] = 14,
) -> LiftDetailResponse:
    if lift not in LIFTS:
        raise HTTPException(status_code=400, detail=f"invalid lift: {lift}")
    c: aiosqlite.Connection = request.app.state.conn
    cat: Catalog = request.app.state.catalog
    await _ensure_user(c, user_id)

    today = datetime.now(UTC).date()
    since_d = today - timedelta(weeks=max(weeks, 8))  # need 8w history for ACWR
    since_ts = _date_to_unix_start(since_d)
    until_ts = _date_to_unix_end(today)

    workouts = await repo.get_workouts_in_window(
        c, user_id=user_id, since_ts=since_ts, until_ts=until_ts
    )
    canonical = LIFT_CANONICAL[lift]

    # Latest bodyweight
    bw_latest = await repo.get_latest_body_weight(c, user_id)
    bw_kg = bw_latest[0] / 1000.0 if bw_latest else None

    pr_by_lift = await _pr_by_lift(c, user_id=user_id, catalog=cat)

    next_meet_row = await repo_pl.get_next_meet(c, user_id=user_id)
    target_kg = 0.0
    if next_meet_row:
        target_kg = {
            "squat": next_meet_row.target_squat_g / 1000.0,
            "bench": next_meet_row.target_bench_g / 1000.0,
            "deadlift": next_meet_row.target_deadlift_g / 1000.0,
        }[lift]

    big3 = compute_big3_summary(
        workouts,
        today=today,
        bodyweight_kg=bw_kg,
        pr_by_lift=pr_by_lift,
        next_meet_targets_kg={lift: target_kg},
        catalog=cat,
    )
    me = next(b for b in big3 if b.lift == lift)

    phases = await repo_pl.list_phases(c, user_id=user_id, since_ts=since_ts, until_ts=until_ts)
    phase_map = phases_to_week_map(phases, weeks=weeks, today=today)
    weekly_raw = compute_lift_weekly(
        workouts, target_group=lift, catalog=cat, weeks=weeks, today=today
    )
    weekly = [
        LiftWeekPoint(
            iso_week=p.iso_week,
            e1rm_kg=p.e1rm_kg,
            tonnage_kg=p.tonnage_kg,
            intensity_pct=p.intensity_pct,
            avg_velocity_ms=p.avg_velocity_ms,
            phase=phase_map.get(p.iso_week, "unscheduled"),
        )
        for p in weekly_raw
    ]

    floor_by_min_reps = best_weight_by_min_reps(
        workouts,
        target_group=lift,
        catalog=cat,
        since=today - timedelta(days=27),
        until=today,
    )
    rm_table = rep_max_table(me.current_e1rm_kg, floor_by_min_reps=floor_by_min_reps)
    rep_max = [RepMaxEntry(reps=r, weight_kg=w) for r, w in rm_table.items()]

    recs = compute_set_recommendations(me.current_e1rm_kg)
    set_recs = [
        SetRecommendationItem(
            name=r.name,
            scheme=r.scheme,
            intensity_pct=r.intensity_pct,
            weight_kg=r.weight_kg,
        )
        for r in recs
    ]

    # All-time PRs from personal_records, also mark if happened on a meet date
    pr_rows = await repo.get_personal_records(
        c, user_id=user_id, canonical_name=canonical, limit=50
    )
    meet_dates = {
        repo_pl.unix_to_date(m.meet_date)
        for m in await repo_pl.list_meets(c, user_id=user_id)
    }
    all_prs = [
        PRItemSchema(
            date=datetime.fromtimestamp(pr.achieved_at, tz=UTC).date(),
            weight_kg=pr.weight_g / 1000.0,
            reps=pr.reps,
            estimated_1rm_kg=pr.estimated_1rm_g / 1000.0,
            is_meet=datetime.fromtimestamp(pr.achieved_at, tz=UTC).date() in meet_dates,
        )
        for pr in pr_rows
    ]

    tech_rows = await repo_pl.list_technique_notes(
        c, user_id=user_id, canonical_name=canonical, limit=10
    )
    tech_notes = [
        TechniqueNoteItem(
            id=t.id,
            recorded_date=repo_pl.unix_to_date(t.recorded_date),
            note_text=t.note_text,
            source=t.source,
        )
        for t in tech_rows
    ]

    # ACWR from this lift's daily tonnage — includes all target_group variants
    # (sumo_deadlift, front_squat, paused_bench, etc.) as raw tonnage.
    lift_tonnage: dict[date, float] = {}
    for w in workouts:
        d = datetime.fromtimestamp(w.performed_at, tz=UTC).date()
        for ex in w.exercises:
            entry = cat.by_canonical(ex.canonical_name or "")
            if entry is None or entry.target_group != lift:
                continue
            for s in ex.sets:
                if s.is_warmup or s.reps <= 0:
                    continue
                lift_tonnage[d] = lift_tonnage.get(d, 0.0) + s.reps * (s.weight_g / 1000.0)
    acwr_r = acwr_from_daily_tonnage(lift_tonnage, today)
    acwr = AcwrSchema(
        acute_7d_kg=acwr_r.acute_7d_kg,
        chronic_28d_avg_kg=acwr_r.chronic_28d_avg_kg,
        ratio=acwr_r.ratio,
        risk_zone=acwr_r.risk_zone,
    )

    return LiftDetailResponse(
        lift=lift,  # type: ignore[arg-type]
        canonical_name=canonical,
        current_e1rm_kg=me.current_e1rm_kg,
        prev_e1rm_kg=me.prev_e1rm_kg,
        delta_pct=me.delta_pct,
        pr_kg=me.pr_kg,
        target_kg=me.target_kg,
        pct_of_bw=me.pct_of_bw,
        weekly=weekly,
        rep_max=rep_max,
        set_recommendations=set_recs,
        all_prs=all_prs,
        technique_notes=tech_notes,
        acwr=acwr,
    )


# ========================================================= GET /api/pl/history


@router.get("/history", response_model=HistoryResponse)
async def history(
    request: Request,
    user_id: Annotated[int, Query(...)],
) -> HistoryResponse:
    c: aiosqlite.Connection = request.app.state.conn
    await _ensure_user(c, user_id)

    meets = await repo_pl.list_meets(c, user_id=user_id)
    summary = compute_meet_history(meets)

    today = datetime.now(UTC).date()
    yr_since = _date_to_unix_start(today - timedelta(days=365))
    yr_until = _date_to_unix_end(today)
    workouts = await repo.get_workouts_in_window(
        c, user_id=user_id, since_ts=yr_since, until_ts=yr_until
    )
    cat: Catalog = request.app.state.catalog
    growth = compute_rm_growth_yoy(workouts, today=today, catalog=cat)

    # PR cards for Big3
    pr_cards: list[PersonalRecordCard] = []
    for lift in LIFTS:
        canonical = LIFT_CANONICAL[lift]
        rows = await repo.get_personal_records(
            c, user_id=user_id, canonical_name=canonical, limit=1
        )
        if rows:
            pr_cards.append(
                PersonalRecordCard(
                    lift=lift,  # type: ignore[arg-type]
                    canonical_name=canonical,
                    weight_kg=rows[0].estimated_1rm_g / 1000.0,
                    date=datetime.fromtimestamp(rows[0].achieved_at, tz=UTC).date(),
                )
            )
        else:
            pr_cards.append(
                PersonalRecordCard(
                    lift=lift,  # type: ignore[arg-type]
                    canonical_name=canonical,
                    weight_kg=0.0,
                    date=None,
                )
            )

    return HistoryResponse(
        kpi=HistoryKpiSchema(
            total_meets=summary.total_meets,
            best_total_kg=summary.best_total_kg,
            best_total_at=summary.best_total_at,
            best_wilks=summary.best_wilks,
            best_dots=summary.best_dots,
            podiums=summary.podiums,
        ),
        meets=[
            MeetEntrySchema(
                id=m.id,
                date=m.date,
                name=m.name,
                category=m.category,
                federation=m.federation,
                bodyweight_kg=m.bodyweight_kg,
                squat_kg=m.squat_kg,
                bench_kg=m.bench_kg,
                deadlift_kg=m.deadlift_kg,
                total_kg=m.total_kg,
                wilks=m.wilks,
                dots=m.dots,
                ipf_gl=m.ipf_gl,
                place=m.place,
                is_gym_meet=m.is_gym_meet,
            )
            for m in summary.meets
        ],
        rm_growth=[
            RmGrowthItem(
                lift=g.lift,  # type: ignore[arg-type]
                start_kg=g.start_kg,
                end_kg=g.end_kg,
                delta_kg=g.delta_kg,
                delta_pct=g.delta_pct,
            )
            for g in growth
        ],
        personal_records=pr_cards,
        best_total_kg=summary.best_total_kg,
        best_gym_total_kg=summary.best_gym_total_kg,
    )


# ========================================================= GET /api/pl/config


@router.get("/config", response_model=dict)
async def config(
    request: Request,
    user_id: Annotated[int, Query(...)],
) -> dict:
    c: aiosqlite.Connection = request.app.state.conn
    await _ensure_user(c, user_id)
    today = datetime.now(UTC).date()
    nm_row = await repo_pl.get_next_meet(c, user_id=user_id)
    nm_echo = next_meet_to_echo(nm_row, today=today)
    phases = await repo_pl.list_phases(c, user_id=user_id)
    bw_latest = await repo.get_latest_body_weight(c, user_id=user_id)
    return {
        "next_meet": (
            NextMeetEchoSchema(
                meet_date=nm_echo.meet_date,
                days_left=nm_echo.days_left,
                name=nm_echo.name,
                category=nm_echo.category,
                federation=nm_echo.federation,
                target_squat_kg=nm_echo.target_squat_kg,
                target_bench_kg=nm_echo.target_bench_kg,
                target_deadlift_kg=nm_echo.target_deadlift_kg,
                target_total_kg=nm_echo.target_total_kg,
                attempts_kg=nm_echo.attempts_kg,
            ).model_dump(mode="json")
            if nm_echo
            else None
        ),
        "phases": [
            PhaseSchema(
                phase_name=p.phase_name,
                start_date=repo_pl.unix_to_date(p.start_date),
                end_date=repo_pl.unix_to_date(p.end_date),
                color_hex=p.color_hex,
            ).model_dump(mode="json")
            for p in phases
        ],
        "bodyweight_kg": bw_latest[0] / 1000.0 if bw_latest else None,
    }


# ========================================================= WRITE endpoints


@router.post("/meets", response_model=dict)
async def create_meet(
    request: Request,
    user_id: Annotated[int, Query(...)],
    body: MeetCreate,
) -> dict:
    c: aiosqlite.Connection = request.app.state.conn
    await _ensure_user(c, user_id)
    total_kg = body.squat_kg + body.bench_kg + body.deadlift_kg
    w = body.wilks if hasattr(body, "wilks") else None
    if body.bodyweight_kg:
        w = wilks_score(total_kg, body.bodyweight_kg, body.is_female)
        d = dots_score(total_kg, body.bodyweight_kg, body.is_female)
        g = ipf_gl_points(total_kg, body.bodyweight_kg, body.is_female)
    else:
        w, d, g = None, None, None
    meet_id = await repo_pl.insert_meet(
        c,
        user_id=user_id,
        meet_date=_date_to_unix_start(body.meet_date),
        name=body.name,
        category=body.category,
        federation=body.federation,
        bodyweight_g=int(body.bodyweight_kg * 1000) if body.bodyweight_kg else None,
        squat_g=int(body.squat_kg * 1000),
        bench_g=int(body.bench_kg * 1000),
        deadlift_g=int(body.deadlift_kg * 1000),
        wilks=w,
        dots=d,
        ipf_gl=g,
        place=body.place,
        is_gym_meet=body.is_gym_meet,
        notes=body.notes,
    )
    return {"id": meet_id}


@router.post("/recovery", response_model=dict)
async def create_recovery(
    request: Request,
    user_id: Annotated[int, Query(...)],
    body: RecoveryCreate,
) -> dict:
    c: aiosqlite.Connection = request.app.state.conn
    await _ensure_user(c, user_id)
    rid = await repo_pl.insert_recovery(
        c,
        user_id=user_id,
        recorded_date=_date_to_unix_start(body.recorded_date),
        sleep_hours=body.sleep_hours,
        hrv_ms=body.hrv_ms,
        rhr_bpm=body.rhr_bpm,
        recovery_pct=body.recovery_pct,
        notes=body.notes,
    )
    return {"id": rid}


@router.post("/niggles", response_model=dict)
async def create_niggle(
    request: Request,
    user_id: Annotated[int, Query(...)],
    body: NiggleCreate,
) -> dict:
    c: aiosqlite.Connection = request.app.state.conn
    await _ensure_user(c, user_id)
    nid = await repo_pl.insert_niggle(
        c,
        user_id=user_id,
        recorded_date=_date_to_unix_start(body.recorded_date),
        body_area=body.body_area,
        severity=body.severity,
        note=body.note,
    )
    return {"id": nid}


@router.put("/next-meet", response_model=dict)
async def update_next_meet(
    request: Request,
    user_id: Annotated[int, Query(...)],
    body: NextMeetUpdate,
) -> dict:
    c: aiosqlite.Connection = request.app.state.conn
    await _ensure_user(c, user_id)
    attempts_g = {
        lift: [int(kg * 1000) for kg in body.attempts_kg.get(lift, [])][:3]
        for lift in ("squat", "bench", "deadlift")
    }
    await repo_pl.upsert_next_meet(
        c,
        user_id=user_id,
        meet_date=_date_to_unix_start(body.meet_date),
        name=body.name,
        category=body.category,
        federation=body.federation,
        target_squat_g=int(body.target_squat_kg * 1000),
        target_bench_g=int(body.target_bench_kg * 1000),
        target_deadlift_g=int(body.target_deadlift_kg * 1000),
        attempts=attempts_g,
    )
    return {"status": "ok"}


@router.post("/bodyweight", response_model=dict)
async def create_bodyweight(
    request: Request,
    user_id: Annotated[int, Query(...)],
    body: BodyweightCreate,
) -> dict:
    c: aiosqlite.Connection = request.app.state.conn
    await _ensure_user(c, user_id)
    await repo.upsert_body_weight(
        c,
        user_id=user_id,
        recorded_at=_date_to_unix_start(body.recorded_date),
        weight_g=int(body.weight_kg * 1000),
    )
    return {"status": "ok"}


# Unused import silenced (it's used in schemas for type annotation consumers)
_ = CANONICAL_TO_LIFT
_ = daily_tonnage
