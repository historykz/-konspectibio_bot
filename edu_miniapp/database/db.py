"""Управление соединением с SQLite (aiosqlite)."""
import aiosqlite

import config

_DB_FILE = str(config.BASE_DIR / config.DB_PATH)
_conn: aiosqlite.Connection | None = None


async def connect() -> aiosqlite.Connection:
    """Открыть единое соединение (по строке возвращаются dict-подобные Row)."""
    global _conn
    if _conn is None:
        _conn = await aiosqlite.connect(_DB_FILE)
        _conn.row_factory = aiosqlite.Row
        await _conn.execute("PRAGMA foreign_keys = ON")
        await _conn.commit()
    return _conn


async def close() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


async def init_db() -> None:
    """Создать таблицы из schema.sql."""
    conn = await connect()
    schema = (config.BASE_DIR / "database" / "schema.sql").read_text(encoding="utf-8")
    await conn.executescript(schema)
    await conn.commit()
