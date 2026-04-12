"""Entrypoint: load config, wire services, start long polling."""

from __future__ import annotations

import asyncio

from pwrbot.bot.app import build_bot, build_dispatcher
from pwrbot.config import load_settings
from pwrbot.db.connection import open_and_bootstrap
from pwrbot.domain.catalog import load_catalog
from pwrbot.llm.ollama_client import OllamaClient
from pwrbot.llm.prompt_loader import PromptLoader
from pwrbot.logging_setup import configure_logging, get_logger
from pwrbot.parsing.llm_parser import LLMParser
from pwrbot.parsing.pipeline import ParsingPipeline
from pwrbot.services.analyze import AnalyzeService
from pwrbot.services.ingest import IngestService
from pwrbot.services.max_query import MaxQueryService


async def _main_async() -> None:
    settings, yaml_cfg = load_settings()
    configure_logging(settings.log_level)
    log = get_logger("pwrbot")
    log.info("starting", model=settings.ollama_model, db=str(settings.db_path))

    conn = await open_and_bootstrap(settings.db_path)
    catalog = load_catalog(settings.exercises_path)
    prompts = PromptLoader(settings.prompts_dir)
    ollama = OllamaClient(
        base_url=settings.ollama_url,
        model=settings.ollama_model,
        timeout_s=settings.ollama_timeout_s,
        max_retries=yaml_cfg.llm.max_retries,
    )
    llm_parser = LLMParser(client=ollama, prompts=prompts, catalog=catalog)
    pipeline = ParsingPipeline(catalog=catalog, cfg=yaml_cfg, llm_parser=llm_parser)
    analyze_svc = AnalyzeService(cfg=yaml_cfg, llm=llm_parser)
    ingest_svc = IngestService(
        pipeline=pipeline, analyzer=analyze_svc, catalog=catalog, cfg=yaml_cfg
    )
    max_query_svc = MaxQueryService(catalog=catalog, cfg=yaml_cfg)

    bot = build_bot(settings.telegram_token)
    dp = build_dispatcher(
        conn=conn,
        ingest=ingest_svc,
        analyze=analyze_svc,
        max_query_svc=max_query_svc,
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
