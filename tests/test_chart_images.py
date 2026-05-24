from __future__ import annotations

from dataclasses import dataclass

import pytest

from pwrbot.bot.handlers.charts import cmd_chart
from pwrbot.db import repo
from pwrbot.services.chart_images import ChartImageService, ChartRenderRequest, get_chart_definition


class FakeFromUser:
    id = 42
    full_name = "Artem"


class FakePhotoMessage:
    from_user = FakeFromUser()

    def __init__(self, text: str) -> None:
        self.text = text
        self.answers: list[str] = []
        self.photos: list[tuple[object, str | None]] = []

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)

    async def answer_photo(self, photo: object, caption: str | None = None, **_: object) -> None:
        self.photos.append((photo, caption))


@dataclass
class FakeChartService:
    calls: list[ChartRenderRequest]

    async def render(self, request: ChartRenderRequest) -> bytes:
        self.calls.append(request)
        return b"\x89PNG\r\n\x1a\nfake"


@pytest.mark.parametrize(
    "chart_id",
    ["overview-tonnage", "overview-intensity", "lift-e1rm", "bodyweight-trend"],
)
def test_known_chart_definitions_exist(chart_id: str) -> None:
    definition = get_chart_definition(chart_id)

    assert definition.id == chart_id
    assert definition.export_path.startswith("/export/chart/")


def test_bodyweight_chart_builds_export_url_without_lift() -> None:
    service = ChartImageService(base_url="http://127.0.0.1:8000")

    url = service.build_export_url(
        ChartRenderRequest(chart_id="bodyweight-trend", user_id=7, weeks=12)
    )

    assert url == "http://127.0.0.1:8000/export/chart/bodyweight-trend?user_id=7&weeks=12"


def test_chart_service_rejects_unknown_chart_ids() -> None:
    service = ChartImageService(base_url="http://127.0.0.1:8000")

    with pytest.raises(ValueError, match="Unknown chart"):
        service.build_export_url(
            ChartRenderRequest(chart_id="http://evil.local/", user_id=1)
        )


@pytest.mark.parametrize(
    "render_request",
    [
        ChartRenderRequest(chart_id="overview-tonnage", user_id=0),
        ChartRenderRequest(chart_id="overview-tonnage", user_id=1, weeks=3),
        ChartRenderRequest(chart_id="overview-tonnage", user_id=1, weeks=53),
        ChartRenderRequest(chart_id="lift-e1rm", user_id=1, lift="curl"),
    ],
)
def test_chart_service_rejects_invalid_render_params(render_request: ChartRenderRequest) -> None:
    service = ChartImageService(base_url="http://127.0.0.1:8000")

    with pytest.raises(ValueError):
        service.build_export_url(render_request)


@pytest.mark.parametrize("base_url", ["pwrbot-dashboard:8000", "ftp://127.0.0.1:8000"])
def test_chart_service_rejects_malformed_base_urls(base_url: str) -> None:
    with pytest.raises(ValueError):
        ChartImageService(base_url=base_url)


def test_chart_service_builds_only_internal_export_urls() -> None:
    service = ChartImageService(base_url="http://127.0.0.1:8000/root/")

    url = service.build_export_url(
        ChartRenderRequest(chart_id="lift-e1rm", user_id=7, weeks=12, lift="bench")
    )

    assert url == "http://127.0.0.1:8000/export/chart/lift-e1rm?user_id=7&weeks=12&lift=bench"


async def test_chart_command_renders_photo_for_existing_telegram_user(conn) -> None:
    user_id = await repo.get_or_create_user(conn, telegram_id=42, display_name="Artem")
    chart_service = FakeChartService(calls=[])
    message = FakePhotoMessage("/chart lift-e1rm bench 12")

    await cmd_chart(message, conn=conn, chart_images=chart_service)  # type: ignore[arg-type]

    assert not message.answers
    assert len(message.photos) == 1
    assert "lift-e1rm" in (message.photos[0][1] or "")
    assert chart_service.calls == [
        ChartRenderRequest(chart_id="lift-e1rm", user_id=user_id, weeks=12, lift="bench")
    ]


async def test_chart_command_renders_bodyweight_photo_with_short_alias(conn) -> None:
    user_id = await repo.get_or_create_user(conn, telegram_id=42, display_name="Artem")
    chart_service = FakeChartService(calls=[])
    message = FakePhotoMessage("/chart bodyweight 12")

    await cmd_chart(message, conn=conn, chart_images=chart_service)  # type: ignore[arg-type]

    assert not message.answers
    assert len(message.photos) == 1
    assert "bodyweight-trend" in (message.photos[0][1] or "")
    assert chart_service.calls == [
        ChartRenderRequest(chart_id="bodyweight-trend", user_id=user_id, weeks=12)
    ]


async def test_chart_command_rejects_unregistered_user_without_rendering(conn) -> None:
    chart_service = FakeChartService(calls=[])
    message = FakePhotoMessage("/chart overview-tonnage 14")

    await cmd_chart(message, conn=conn, chart_images=chart_service)  # type: ignore[arg-type]

    assert chart_service.calls == []
    assert message.photos == []
    assert "Сначала напиши /start" in message.answers[0]


async def test_chart_command_rejects_invalid_weeks_without_rendering(conn) -> None:
    await repo.get_or_create_user(conn, telegram_id=42, display_name="Artem")
    chart_service = FakeChartService(calls=[])
    message = FakePhotoMessage("/chart overview-tonnage 99")

    await cmd_chart(message, conn=conn, chart_images=chart_service)  # type: ignore[arg-type]

    assert chart_service.calls == []
    assert message.photos == []
    assert "weeks" in message.answers[0]


async def test_chart_command_rejects_unknown_chart_without_rendering(conn) -> None:
    await repo.get_or_create_user(conn, telegram_id=42, display_name="Artem")
    chart_service = FakeChartService(calls=[])
    message = FakePhotoMessage("/chart http://evil.local/")

    await cmd_chart(message, conn=conn, chart_images=chart_service)  # type: ignore[arg-type]

    assert chart_service.calls == []
    assert message.photos == []
    assert "Неизвестный график" in message.answers[0]
