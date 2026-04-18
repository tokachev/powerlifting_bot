"""FastAPI application factory for the pwrbot dashboard.

`create_app(catalog)` builds the app and routes; the caller is responsible for
setting `app.state.conn` to an `aiosqlite.Connection` before serving requests.
Tests assign a test connection directly. Production wires it through `_lifespan`.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import aiosqlite
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pwrbot.api.routes_powerlifting import router as pl_router
from pwrbot.api.schemas import (
    BodyWeightEntry,
    CalendarDaySchema,
    CalendarResponse,
    DashboardFiltersEcho,
    DashboardResponse,
    E1RMPointSchema,
    E1RMTrendResponse,
    ExerciseInfo,
    ExerciseSessionSchema,
    FrequencyCellSchema,
    FrequencyResponse,
    PerExerciseResponse,
    PersonalRecordSchema,
    PRsResponse,
    RepBucketSchema,
    RepDistributionResponse,
    SetDetailSchema,
    TonnageTrendResponse,
    TonnageWeekSchema,
    UserInfo,
    VolumeLandmarkSchema,
    WeeklySetsBucketSchema,
    WeeklySetsResponse,
)
from pwrbot.config import YamlConfig, load_yaml_config
from pwrbot.db import repo
from pwrbot.db.connection import bootstrap
from pwrbot.domain.catalog import (
    VALID_MUSCLE_GROUPS,
    Catalog,
    load_catalog,
)
from pwrbot.metrics.calendar import compute_calendar
from pwrbot.metrics.e1rm_trend import compute_e1rm_trend
from pwrbot.metrics.frequency import compute_frequency
from pwrbot.metrics.per_exercise import compute_per_exercise
from pwrbot.metrics.rep_distribution import compute_rep_distribution
from pwrbot.metrics.tonnage_trend import compute_tonnage_trend
from pwrbot.metrics.weekly_sets import compute_weekly_sets
from pwrbot.services.reporting import FilterSpec, build_dashboard

VALID_MOVEMENT_PATTERNS = frozenset(
    {"squat", "hinge", "push", "pull", "carry", "core", "accessory"}
)


def _date_to_unix_start(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


def _date_to_unix_end(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC).timestamp())


def _settings_paths() -> tuple[Path, Path]:
    db_path = Path(os.environ.get("PWRBOT_DB_PATH", "./data/pwrbot.db"))
    exercises_path = Path(
        os.environ.get("PWRBOT_EXERCISES_PATH", "./config/exercises.yaml")
    )
    return db_path, exercises_path


@asynccontextmanager
async def _lifespan(app: FastAPI):
    db_path, _ = _settings_paths()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Open in autocommit mode (isolation_level=None) so the API never holds an
    # implicit read transaction. Writes made by the bot process become visible
    # on the next SELECT, otherwise we'd serve stale snapshots.
    conn = await aiosqlite.connect(db_path, isolation_level=None)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    # Skip bootstrap — the bot process (r/w) owns schema migrations.
    # Dashboard volume is mounted read-only, so DDL would fail here.
    app.state.conn = conn
    try:
        yield
    finally:
        await conn.close()


def create_app(
    catalog: Catalog,
    *,
    yaml_config: YamlConfig | None = None,
    lifespan: bool = False,
) -> FastAPI:
    """Build the dashboard FastAPI app.

    Args:
        catalog: pre-loaded exercise catalog (state).
        yaml_config: loaded YAML config (thresholds, landmarks). Optional for
            backward-compatible tests that don't need metric endpoints.
        lifespan: when True, attach the production lifespan that opens the SQLite
            connection. Tests pass False and assign `app.state.conn` themselves.
    """
    app = FastAPI(
        title="pwrbot dashboard",
        version="0.1.0",
        lifespan=_lifespan if lifespan else None,
    )
    app.state.catalog = catalog
    app.state.yaml_config = yaml_config

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["*"],
    )

    app.include_router(pl_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/users", response_model=list[UserInfo])
    async def list_users(request: Request) -> list[UserInfo]:
        c: aiosqlite.Connection = request.app.state.conn
        async with c.execute(
            "SELECT id, telegram_id, display_name FROM users ORDER BY id ASC"
        ) as cur:
            rows = await cur.fetchall()
        return [
            UserInfo(
                id=int(r["id"]),
                telegram_id=int(r["telegram_id"]),
                display_name=r["display_name"],
            )
            for r in rows
        ]

    @app.get("/api/catalog", response_model=list[ExerciseInfo])
    async def list_catalog(request: Request) -> list[ExerciseInfo]:
        cat: Catalog = request.app.state.catalog
        return [
            ExerciseInfo(
                canonical_name=e.canonical_name,
                movement_pattern=e.movement_pattern,
                target_group=e.target_group,
                muscle_group=e.muscle_group,
            )
            for e in cat.entries
        ]

    @app.get("/api/dashboard", response_model=DashboardResponse)
    async def dashboard(
        request: Request,
        user_id: Annotated[int, Query(...)],
        since: Annotated[date | None, Query()] = None,
        until: Annotated[date | None, Query()] = None,
        muscle_groups: Annotated[list[str] | None, Query()] = None,
        movement_patterns: Annotated[list[str] | None, Query()] = None,
        target_only: Annotated[bool, Query()] = False,
    ) -> DashboardResponse:
        today = datetime.now(UTC).date()
        until_d = until or today
        since_d = since or (until_d - timedelta(days=27))
        if since_d > until_d:
            raise HTTPException(status_code=400, detail="since must be <= until")

        mg = muscle_groups or []
        for v in mg:
            if v not in VALID_MUSCLE_GROUPS:
                raise HTTPException(
                    status_code=400, detail=f"invalid muscle_group: {v}"
                )

        mp = movement_patterns or []
        for v in mp:
            if v not in VALID_MOVEMENT_PATTERNS:
                raise HTTPException(
                    status_code=400, detail=f"invalid movement_pattern: {v}"
                )

        c: aiosqlite.Connection = request.app.state.conn
        cat: Catalog = request.app.state.catalog

        async with c.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ) as cur:
            if (await cur.fetchone()) is None:
                raise HTTPException(status_code=404, detail="user not found")

        data = await build_dashboard(
            c,
            user_id=user_id,
            since_ts=_date_to_unix_start(since_d),
            until_ts=_date_to_unix_end(until_d),
            filter_spec=FilterSpec(
                muscle_groups=mg,
                movement_patterns=mp,
                target_only=target_only,
            ),
            catalog=cat,
        )

        return DashboardResponse(
            days=data.days,
            kpsh_by_bucket=data.kpsh_by_bucket,
            intensity_kg=data.intensity_kg,
            kpsh_by_muscle=data.kpsh_by_muscle,
            kpsh_by_pattern=data.kpsh_by_pattern,
            total_workouts=data.total_workouts,
            total_kpsh=data.total_kpsh,
            avg_intensity_kg=data.avg_intensity_kg,
            filters=DashboardFiltersEcho(
                user_id=user_id,
                since=since_d,
                until=until_d,
                muscle_groups=mg,
                movement_patterns=mp,
                target_only=target_only,
            ),
        )

    @app.get("/api/e1rm", response_model=E1RMTrendResponse)
    async def e1rm_trend(
        request: Request,
        user_id: Annotated[int, Query(...)],
        exercises: Annotated[list[str], Query(...)],
        since: Annotated[date | None, Query()] = None,
        until: Annotated[date | None, Query()] = None,
    ) -> E1RMTrendResponse:
        today = datetime.now(UTC).date()
        until_d = until or today
        since_d = since or (until_d - timedelta(days=89))
        if since_d > until_d:
            raise HTTPException(status_code=400, detail="since must be <= until")

        c: aiosqlite.Connection = request.app.state.conn
        async with c.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ) as cur:
            if (await cur.fetchone()) is None:
                raise HTTPException(status_code=404, detail="user not found")

        workouts = await repo.get_workouts_in_window(
            c,
            user_id=user_id,
            since_ts=_date_to_unix_start(since_d),
            until_ts=_date_to_unix_end(until_d),
        )
        points = compute_e1rm_trend(workouts, exercises)
        return E1RMTrendResponse(
            points=[
                E1RMPointSchema(
                    date=p.date,
                    canonical_name=p.canonical_name,
                    estimated_1rm_kg=p.estimated_1rm_kg,
                    best_weight_kg=p.best_weight_kg,
                    best_reps=p.best_reps,
                )
                for p in points
            ]
        )

    @app.get("/api/weekly-sets", response_model=WeeklySetsResponse)
    async def weekly_sets(
        request: Request,
        user_id: Annotated[int, Query(...)],
        since: Annotated[date | None, Query()] = None,
        until: Annotated[date | None, Query()] = None,
    ) -> WeeklySetsResponse:
        today = datetime.now(UTC).date()
        until_d = until or today
        since_d = since or (until_d - timedelta(days=83))  # 12 weeks
        if since_d > until_d:
            raise HTTPException(status_code=400, detail="since must be <= until")

        c: aiosqlite.Connection = request.app.state.conn
        async with c.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ) as cur:
            if (await cur.fetchone()) is None:
                raise HTTPException(status_code=404, detail="user not found")

        cat: Catalog = request.app.state.catalog
        cfg: YamlConfig | None = request.app.state.yaml_config

        workouts = await repo.get_workouts_in_window(
            c,
            user_id=user_id,
            since_ts=_date_to_unix_start(since_d),
            until_ts=_date_to_unix_end(until_d),
        )

        if cfg is None:
            raise HTTPException(status_code=500, detail="yaml_config not loaded")

        buckets = compute_weekly_sets(workouts, cat, cfg.thresholds)
        landmarks = {
            k: VolumeLandmarkSchema(mev=v.mev, mav=v.mav, mrv=v.mrv)
            for k, v in cfg.volume_landmarks.items()
        }
        return WeeklySetsResponse(
            buckets=[
                WeeklySetsBucketSchema(
                    iso_week=b.iso_week,
                    muscle_group=b.muscle_group,
                    hard_sets=b.hard_sets,
                )
                for b in buckets
            ],
            landmarks=landmarks,
        )

    @app.get("/api/tonnage-trend", response_model=TonnageTrendResponse)
    async def tonnage_trend(
        request: Request,
        user_id: Annotated[int, Query(...)],
        since: Annotated[date | None, Query()] = None,
        until: Annotated[date | None, Query()] = None,
    ) -> TonnageTrendResponse:
        today = datetime.now(UTC).date()
        until_d = until or today
        since_d = since or (until_d - timedelta(days=83))  # 12 weeks
        if since_d > until_d:
            raise HTTPException(status_code=400, detail="since must be <= until")

        c: aiosqlite.Connection = request.app.state.conn
        async with c.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ) as cur:
            if (await cur.fetchone()) is None:
                raise HTTPException(status_code=404, detail="user not found")

        workouts = await repo.get_workouts_in_window(
            c,
            user_id=user_id,
            since_ts=_date_to_unix_start(since_d),
            until_ts=_date_to_unix_end(until_d),
        )
        weeks = compute_tonnage_trend(workouts)
        return TonnageTrendResponse(
            weeks=[
                TonnageWeekSchema(iso_week=w.iso_week, tonnage_kg=w.tonnage_kg)
                for w in weeks
            ]
        )

    @app.get("/api/calendar", response_model=CalendarResponse)
    async def calendar(
        request: Request,
        user_id: Annotated[int, Query(...)],
        since: Annotated[date | None, Query()] = None,
        until: Annotated[date | None, Query()] = None,
    ) -> CalendarResponse:
        today = datetime.now(UTC).date()
        until_d = until or today
        since_d = since or (until_d - timedelta(days=364))
        if since_d > until_d:
            raise HTTPException(status_code=400, detail="since must be <= until")

        c: aiosqlite.Connection = request.app.state.conn
        async with c.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ) as cur:
            if (await cur.fetchone()) is None:
                raise HTTPException(status_code=404, detail="user not found")

        workouts = await repo.get_workouts_in_window(
            c,
            user_id=user_id,
            since_ts=_date_to_unix_start(since_d),
            until_ts=_date_to_unix_end(until_d),
        )
        days = compute_calendar(workouts)
        return CalendarResponse(
            days=[
                CalendarDaySchema(
                    date=d.date,
                    workout_count=d.workout_count,
                    total_sets=d.total_sets,
                    total_tonnage_kg=d.total_tonnage_kg,
                )
                for d in days
            ]
        )

    @app.get("/api/prs", response_model=PRsResponse)
    async def personal_records(
        request: Request,
        user_id: Annotated[int, Query(...)],
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> PRsResponse:
        c: aiosqlite.Connection = request.app.state.conn
        async with c.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ) as cur:
            if (await cur.fetchone()) is None:
                raise HTTPException(status_code=404, detail="user not found")

        rows = await repo.get_personal_records(c, user_id=user_id, limit=limit)
        return PRsResponse(
            records=[
                PersonalRecordSchema(
                    date=datetime.fromtimestamp(r.achieved_at, tz=UTC).date(),
                    canonical_name=r.canonical_name,
                    pr_type=r.pr_type,
                    weight_kg=r.weight_g / 1000.0,
                    reps=r.reps,
                    estimated_1rm_kg=r.estimated_1rm_g / 1000.0,
                    previous_1rm_kg=(
                        r.previous_value_g / 1000.0
                        if r.previous_value_g is not None
                        else None
                    ),
                )
                for r in rows
            ]
        )

    @app.get("/api/per-exercise", response_model=PerExerciseResponse)
    async def per_exercise(
        request: Request,
        user_id: Annotated[int, Query(...)],
        exercise: Annotated[str, Query(...)],
        since: Annotated[date | None, Query()] = None,
        until: Annotated[date | None, Query()] = None,
    ) -> PerExerciseResponse:
        today = datetime.now(UTC).date()
        until_d = until or today
        since_d = since or (until_d - timedelta(days=89))
        if since_d > until_d:
            raise HTTPException(status_code=400, detail="since must be <= until")

        c: aiosqlite.Connection = request.app.state.conn
        async with c.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ) as cur:
            if (await cur.fetchone()) is None:
                raise HTTPException(status_code=404, detail="user not found")

        workouts = await repo.get_workouts_in_window(
            c,
            user_id=user_id,
            since_ts=_date_to_unix_start(since_d),
            until_ts=_date_to_unix_end(until_d),
        )
        sessions = compute_per_exercise(workouts, exercise)
        return PerExerciseResponse(
            sessions=[
                ExerciseSessionSchema(
                    date=s.date,
                    best_e1rm_kg=s.best_e1rm_kg,
                    total_volume_kg=s.total_volume_kg,
                    sets=[
                        SetDetailSchema(
                            reps=sd.reps,
                            weight_kg=sd.weight_kg,
                            rpe=sd.rpe,
                            is_warmup=sd.is_warmup,
                            estimated_1rm_kg=sd.estimated_1rm_kg,
                        )
                        for sd in s.sets
                    ],
                )
                for s in sessions
            ]
        )

    @app.get("/api/rep-distribution", response_model=RepDistributionResponse)
    async def rep_distribution(
        request: Request,
        user_id: Annotated[int, Query(...)],
        canonical_name: Annotated[str | None, Query()] = None,
        since: Annotated[date | None, Query()] = None,
        until: Annotated[date | None, Query()] = None,
    ) -> RepDistributionResponse:
        today = datetime.now(UTC).date()
        until_d = until or today
        since_d = since or (until_d - timedelta(days=89))
        if since_d > until_d:
            raise HTTPException(status_code=400, detail="since must be <= until")

        c: aiosqlite.Connection = request.app.state.conn
        async with c.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ) as cur:
            if (await cur.fetchone()) is None:
                raise HTTPException(status_code=404, detail="user not found")

        workouts = await repo.get_workouts_in_window(
            c,
            user_id=user_id,
            since_ts=_date_to_unix_start(since_d),
            until_ts=_date_to_unix_end(until_d),
        )
        buckets = compute_rep_distribution(workouts, canonical_name)
        return RepDistributionResponse(
            buckets=[
                RepBucketSchema(
                    rep_range=b.rep_range,
                    set_count=b.set_count,
                    rep_count=b.rep_count,
                )
                for b in buckets
            ]
        )

    @app.get("/api/frequency", response_model=FrequencyResponse)
    async def frequency(
        request: Request,
        user_id: Annotated[int, Query(...)],
        since: Annotated[date | None, Query()] = None,
        until: Annotated[date | None, Query()] = None,
    ) -> FrequencyResponse:
        today = datetime.now(UTC).date()
        until_d = until or today
        since_d = since or (until_d - timedelta(days=83))
        if since_d > until_d:
            raise HTTPException(status_code=400, detail="since must be <= until")

        c: aiosqlite.Connection = request.app.state.conn
        async with c.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ) as cur:
            if (await cur.fetchone()) is None:
                raise HTTPException(status_code=404, detail="user not found")

        cat: Catalog = request.app.state.catalog
        workouts = await repo.get_workouts_in_window(
            c,
            user_id=user_id,
            since_ts=_date_to_unix_start(since_d),
            until_ts=_date_to_unix_end(until_d),
        )
        cells = compute_frequency(workouts, cat)
        return FrequencyResponse(
            cells=[
                FrequencyCellSchema(
                    iso_week=cell.iso_week,
                    muscle_group=cell.muscle_group,
                    sessions=cell.sessions,
                )
                for cell in cells
            ]
        )

    @app.get("/api/body_weight", response_model=list[BodyWeightEntry])
    async def body_weight_history(
        request: Request,
        user_id: Annotated[int, Query(...)],
        since: Annotated[date | None, Query()] = None,
        until: Annotated[date | None, Query()] = None,
    ) -> list[BodyWeightEntry]:
        today = datetime.now(UTC).date()
        until_d = until or today
        since_d = since or (until_d - timedelta(days=89))
        if since_d > until_d:
            raise HTTPException(status_code=400, detail="since must be <= until")

        c: aiosqlite.Connection = request.app.state.conn
        async with c.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ) as cur:
            if (await cur.fetchone()) is None:
                raise HTTPException(status_code=404, detail="user not found")

        rows = await repo.get_body_weight_history(
            c, user_id=user_id,
            since_ts=_date_to_unix_start(since_d),
            until_ts=_date_to_unix_end(until_d),
        )
        return [
            BodyWeightEntry(
                date=datetime.fromtimestamp(ts, tz=UTC).date(),
                weight_kg=wg / 1000.0,
            )
            for ts, wg in rows
        ]

    # Static SPA mount in production. Must come AFTER all /api routes so that
    # /api/* keeps routing to FastAPI handlers, not to index.html.
    static_dir = Path(os.environ.get("DASHBOARD_STATIC_DIR", "dashboard/dist"))
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


def build_production_app() -> FastAPI:
    """Entrypoint used by `python -m pwrbot.api`. Reads paths from env vars."""
    _, exercises_path = _settings_paths()
    config_path = Path(os.environ.get("PWRBOT_CONFIG_PATH", "./config/settings.yaml"))
    catalog = load_catalog(exercises_path)
    yaml_config = load_yaml_config(config_path)
    return create_app(catalog, yaml_config=yaml_config, lifespan=True)
