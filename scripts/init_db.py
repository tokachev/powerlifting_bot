"""Initialize the SQLite database file from schema.sql.

Usage:
    python scripts/init_db.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from pwrbot.config import Settings
from pwrbot.db.connection import open_and_bootstrap


async def _main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    db_path: Path = settings.db_path
    conn = await open_and_bootstrap(db_path)
    await conn.close()
    print(f"Initialized DB at {db_path}")


if __name__ == "__main__":
    asyncio.run(_main())
