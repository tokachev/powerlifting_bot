"""Telegram chart image rendering via locked-down dashboard export routes."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit


@dataclass(frozen=True, slots=True)
class ChartDefinition:
    id: str
    title: str
    export_path: str
    requires_lift: bool = False


@dataclass(frozen=True, slots=True)
class ChartRenderRequest:
    chart_id: str
    user_id: int
    weeks: int = 14
    lift: str | None = None


CHARTS: tuple[ChartDefinition, ...] = (
    ChartDefinition(
        id="overview-tonnage",
        title="Тоннаж по лифтам",
        export_path="/export/chart/overview-tonnage",
    ),
    ChartDefinition(
        id="overview-intensity",
        title="Интенсивность по лифтам",
        export_path="/export/chart/overview-intensity",
    ),
    ChartDefinition(
        id="bodyweight-trend",
        title="График веса тела",
        export_path="/export/chart/bodyweight-trend",
    ),
    ChartDefinition(
        id="lift-e1rm",
        title="e1RM по упражнению",
        export_path="/export/chart/lift-e1rm",
        requires_lift=True,
    ),
    ChartDefinition(
        id="lift-tonnage",
        title="Недельный тоннаж упражнения",
        export_path="/export/chart/lift-tonnage",
        requires_lift=True,
    ),
    ChartDefinition(
        id="lift-intensity",
        title="Интенсивность упражнения",
        export_path="/export/chart/lift-intensity",
        requires_lift=True,
    ),
)

_CHART_BY_ID = {c.id: c for c in CHARTS}
_VALID_LIFTS = {"squat", "bench", "deadlift"}


def get_chart_definition(chart_id: str) -> ChartDefinition:
    try:
        return _CHART_BY_ID[chart_id]
    except KeyError as exc:
        raise ValueError(f"Unknown chart: {chart_id}") from exc


def list_chart_definitions() -> tuple[ChartDefinition, ...]:
    return CHARTS


class ChartImageService:
    """Render whitelisted dashboard charts as PNG screenshots.

    The service accepts only chart IDs from CHARTS and always builds a URL under
    the configured internal dashboard base URL. It never accepts arbitrary URLs.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_ms: int = 15_000,
    ) -> None:
        raw_base = base_url or os.environ.get("PWRBOT_DASHBOARD_INTERNAL_URL") or "http://127.0.0.1:8000"
        parts = urlsplit(raw_base)
        if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
            raise ValueError("dashboard base_url must be an http(s) URL with a host and no credentials")
        self._base_url = urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
        self._username = username if username is not None else os.environ.get("PWRBOT_DASHBOARD_USERNAME")
        self._password = password if password is not None else os.environ.get("PWRBOT_DASHBOARD_PASSWORD")
        self._timeout_ms = timeout_ms
        self._semaphore = asyncio.Semaphore(1)

    def build_export_url(self, request: ChartRenderRequest) -> str:
        definition = get_chart_definition(request.chart_id)
        if request.user_id <= 0:
            raise ValueError("user_id must be positive")
        if request.weeks < 4 or request.weeks > 52:
            raise ValueError("weeks must be between 4 and 52")
        if definition.requires_lift and request.lift not in _VALID_LIFTS:
            raise ValueError("lift must be one of: squat, bench, deadlift")
        query: dict[str, str | int] = {
            "user_id": request.user_id,
            "weeks": request.weeks,
        }
        if request.lift is not None:
            if request.lift not in _VALID_LIFTS:
                raise ValueError("lift must be one of: squat, bench, deadlift")
            query["lift"] = request.lift
        return urljoin(self._base_url, definition.export_path.lstrip("/")) + "?" + urlencode(query)

    async def render(self, request: ChartRenderRequest) -> bytes:
        async with self._semaphore:
            return await self._render_locked(request)

    async def _render_locked(self, request: ChartRenderRequest) -> bytes:
        url = self.build_export_url(request)
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - depends on runtime optional extra
            raise RuntimeError(
                "Playwright is required for chart rendering. Install it and run `playwright install chromium`."
            ) from exc

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                context_kwargs = {}
                if self._username and self._password:
                    context_kwargs["http_credentials"] = {
                        "username": self._username,
                        "password": self._password,
                    }
                context = await browser.new_context(
                    viewport={"width": 1100, "height": 720},
                    device_scale_factor=2,
                    **context_kwargs,
                )
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=self._timeout_ms)
                frame = page.locator('[data-chart-export]').first
                await frame.wait_for(state="visible", timeout=self._timeout_ms)
                status = await frame.get_attribute("data-chart-export")
                if status != "ready":
                    raise RuntimeError("dashboard export route did not become ready")
                chart = page.locator('[data-chart-export-content]').first
                await chart.wait_for(state="visible", timeout=self._timeout_ms)
                return await chart.screenshot(type="png")
            finally:
                await browser.close()
