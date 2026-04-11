"""Uvicorn entrypoint: `python -m pwrbot.api`."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("PWRBOT_API_HOST", "127.0.0.1")
    port = int(os.environ.get("PWRBOT_API_PORT", "8000"))
    uvicorn.run(
        "pwrbot.api.main:build_production_app",
        host=host,
        port=port,
        factory=True,
        log_level=os.environ.get("PWRBOT_API_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
