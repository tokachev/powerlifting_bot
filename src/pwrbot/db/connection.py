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
    await _apply_migrations(conn)
    await conn.commit()


async def _apply_migrations(conn: aiosqlite.Connection) -> None:
    """Apply ad-hoc migrations for tables that existed before a column was added.

    SQLite's CREATE TABLE IF NOT EXISTS does not add columns to pre-existing tables,
    so we inspect PRAGMA table_info and ALTER TABLE ADD COLUMN where needed.
    """
    await _ensure_column(conn, table="set_entries", column="bar_velocity_ms", ddl="REAL")


async def _ensure_column(
    conn: aiosqlite.Connection, *, table: str, column: str, ddl: str
) -> None:
    async with conn.execute(f"PRAGMA table_info({table})") as cur:
        rows = await cur.fetchall()
    existing = {row[1] for row in rows}
    if column in existing:
        return
    await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


async def open_and_bootstrap(db_path: Path) -> aiosqlite.Connection:
    conn = await connect(db_path)
    await bootstrap(conn)
    return conn
