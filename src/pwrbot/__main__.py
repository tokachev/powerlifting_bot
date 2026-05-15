"""Entrypoint: load config, wire services, start long polling."""

from __future__ import annotations

import asyncio

import httpx

from pwrbot.bot.app import build_bot, build_dispatcher
from pwrbot.config import load_settings
from pwrbot.db.connection import open_and_bootstrap
from pwrbot.domain.catalog import load_catalog
from pwrbot.llm.codex_client import CodexClient
from pwrbot.llm.ollama_client import OllamaClient
from pwrbot.llm.prompt_loader import PromptLoader
from pwrbot.logging_setup import configure_logging, get_logger
from pwrbot.parsing.llm_parser import LLMParser
from pwrbot.parsing.pipeline import ParsingPipeline
from pwrbot.services.analyze import AnalyzeService
from pwrbot.services.ingest import IngestService
from pwrbot.services.max_query import MaxQueryService
from pwrbot.services.technique import TechniqueAnalysisService


def _readyz_url(ws_url: str) -> str:
    if ws_url.startswith("wss://"):
        base = "https://" + ws_url[len("wss://") :]
    elif ws_url.startswith("ws://"):
        base = "http://" + ws_url[len("ws://") :]
    else:
        base = ws_url
    return base.rstrip("/") + "/readyz"


async def _log_codex_ready(ws_url: str) -> None:
    log = get_logger("pwrbot")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(_readyz_url(ws_url))
            resp.raise_for_status()
    except Exception as exc:
        log.warning("codex_ready_failed", error=str(exc))
        return
    log.info("codex_ready")


async def _main_async() -> None:
    settings, yaml_cfg = load_settings()
    configure_logging(settings.log_level)
    log = get_logger("pwrbot")
    log.info(
        "starting",
        model=settings.ollama_model,
        db=str(settings.db_path),
        codex_enabled=settings.codex_enabled,
        gemma_analysis_enabled=settings.gemma_analysis_enabled,
    )

    conn = await open_and_bootstrap(settings.db_path)
    catalog = load_catalog(settings.exercises_path)
    prompts = PromptLoader(settings.prompts_dir)
    ollama = OllamaClient(
        base_url=settings.ollama_url,
        model=settings.ollama_model,
        timeout_s=settings.ollama_timeout_s,
        max_retries=yaml_cfg.llm.max_retries,
    )
    codex = None
    if settings.codex_enabled:
        codex = CodexClient(
            ws_url=settings.codex_ws_url,
            token_file_path=settings.codex_token_file,
            model=settings.codex_model or yaml_cfg.llm.codex.model,
        )
        await _log_codex_ready(settings.codex_ws_url)
    llm_parser = LLMParser(client=ollama, prompts=prompts, catalog=catalog)
    pipeline = ParsingPipeline(catalog=catalog, cfg=yaml_cfg, llm_parser=llm_parser)
    analyze_svc = AnalyzeService(
        cfg=yaml_cfg,
        llm=llm_parser,
        codex=codex,
        gemma_enabled=settings.gemma_analysis_enabled,
    )
    ingest_svc = IngestService(
        pipeline=pipeline, analyzer=analyze_svc, catalog=catalog, cfg=yaml_cfg
    )
    max_query_svc = MaxQueryService(catalog=catalog, cfg=yaml_cfg)
    technique_svc = TechniqueAnalysisService(
        ollama=ollama,
        prompts=prompts,
        vision_model=yaml_cfg.vision.model,
        vision_timeout_s=yaml_cfg.vision.timeout_s,
        max_frames=yaml_cfg.vision.max_frames,
        resize_width=yaml_cfg.vision.resize_width,
        max_video_duration_s=yaml_cfg.vision.max_video_duration_s,
    )

    bot = build_bot(settings.telegram_token)
    dp = build_dispatcher(
        conn=conn,
        ingest=ingest_svc,
        analyze=analyze_svc,
        max_query_svc=max_query_svc,
        technique_svc=technique_svc,
        yaml_config=yaml_cfg,
        catalog=catalog,
    )

    try:
        await dp.start_polling(bot)
    finally:
        await ollama.aclose()
        await bot.session.close()
        await conn.close()


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
