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

from pwrbot.api.schemas import (
    DashboardFiltersEcho,
    DashboardResponse,
    ExerciseInfo,
    UserInfo,
)
from pwrbot.db.connection import bootstrap
from pwrbot.domain.catalog import (
    VALID_MUSCLE_GROUPS,
    Catalog,
    load_catalog,
)
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
    await bootstrap(conn)
    app.state.conn = conn
    try:
        yield
    finally:
        await conn.close()


def create_app(catalog: Catalog, *, lifespan: bool = False) -> FastAPI:
    """Build the dashboard FastAPI app.

    Args:
        catalog: pre-loaded exercise catalog (state).
        lifespan: when True, attach the production lifespan that opens the SQLite
            connection. Tests pass False and assign `app.state.conn` themselves.
    """
    app = FastAPI(
        title="pwrbot dashboard",
        version="0.1.0",
        lifespan=_lifespan if lifespan else None,
    )
    app.state.catalog = catalog

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

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

    # Static SPA mount in production. Must come AFTER all /api routes so that
    # /api/* keeps routing to FastAPI handlers, not to index.html.
    static_dir = Path(os.environ.get("DASHBOARD_STATIC_DIR", "dashboard/dist"))
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


def build_production_app() -> FastAPI:
    """Entrypoint used by `python -m pwrbot.api`. Reads paths from env vars."""
    _, exercises_path = _settings_paths()
    catalog = load_catalog(exercises_path)
    return create_app(catalog, lifespan=True)
