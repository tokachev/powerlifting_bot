"""aiosqlite connection factory and schema bootstrap."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


async def connect(db_path: Path) -> aiosqlite.Connection:
    """Open a connection with FK enforcement enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    return conn


async def bootstrap(conn: aiosqlite.Connection) -> None:
    """Apply schema.sql on an open connection (idempotent)."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    await conn.executescript(schema)
    await conn.commit()


async def open_and_bootstrap(db_path: Path) -> aiosqlite.Connection:
    conn = await connect(db_path)
    await bootstrap(conn)
    return conn
