import aiosqlite
from datetime import datetime, timezone
from config import DB_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT UNIQUE,
                added_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number INTEGER UNIQUE NOT NULL,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.commit()


# ---------- STUDENTS ----------

async def add_student(telegram_id: int | None = None, username: str | None = None) -> bool:
    """ÐÐ¾Ð±Ð°Ð²Ð¸ÑÑ ÑÑÐµÐ½Ð¸ÐºÐ° Ð¿Ð¾ ID Ð¸Ð»Ð¸ @username. ÐÐ¾Ð·Ð²ÑÐ°ÑÐ°ÐµÑ True ÐµÑÐ»Ð¸ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½, False ÐµÑÐ»Ð¸ ÑÐ¶Ðµ Ð±ÑÐ»."""
    if not telegram_id and not username:
        return False
    username = username.lstrip("@").lower() if username else None
    now = _now()

    async with aiosqlite.connect(DB_PATH) as db:
        # Ð¿ÑÐ¾Ð²ÐµÑÑÐµÐ¼ ÑÑÑÐµÑÑÐ²Ð¾Ð²Ð°Ð½Ð¸Ðµ
        if telegram_id:
            cur = await db.execute("SELECT id FROM students WHERE telegram_id = ?", (telegram_id,))
            if await cur.fetchone():
                return False
        if username:
            cur = await db.execute("SELECT id FROM students WHERE username = ?", (username,))
            if await cur.fetchone():
                return False

        try:
            await db.execute(
                "INSERT INTO students (telegram_id, username, added_at) VALUES (?, ?, ?)",
                (telegram_id, username, now),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_student(telegram_id: int | None = None, username: str | None = None) -> bool:
    username = username.lstrip("@").lower() if username else None
    async with aiosqlite.connect(DB_PATH) as db:
        if telegram_id:
            cur = await db.execute("DELETE FROM students WHERE telegram_id = ?", (telegram_id,))
        else:
            cur = await db.execute("DELETE FROM students WHERE username = ?", (username,))
        await db.commit()
        return cur.rowcount > 0


async def is_student(telegram_id: int, username: str | None = None) -> bool:
    username = username.lstrip("@").lower() if username else None
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM students WHERE telegram_id = ?", (telegram_id,))
        if await cur.fetchone():
            return True
        if username:
            cur = await db.execute("SELECT id FROM students WHERE username = ?", (username,))
            if await cur.fetchone():
                # Ð´Ð¾ÑÑÑÐ°Ð½Ð°Ð²Ð»Ð¸Ð²Ð°ÐµÐ¼ telegram_id, ÑÑÐ¾Ð±Ñ Ð±ÑÑÑÑÐµÐµ Ð½Ð°ÑÐ¾Ð´Ð¸ÑÑ Ð´Ð°Ð»ÑÑÐµ
                await db.execute(
                    "UPDATE students SET telegram_id = ? WHERE username = ? AND telegram_id IS NULL",
                    (telegram_id, username),
                )
                await db.commit()
                return True
    return False


async def list_students() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT telegram_id, username, added_at FROM students ORDER BY id")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---------- NOTES ----------

async def get_note(number: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM notes WHERE number = ?", (number,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def save_note(number: int, title: str, file_path: str, file_id: str | None) -> None:
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        existing = await db.execute("SELECT id FROM notes WHERE number = ?", (number,))
        if await existing.fetchone():
            await db.execute(
                "UPDATE notes SET title = ?, file_path = ?, file_id = ?, updated_at = ? WHERE number = ?",
                (title, file_path, file_id, now, number),
            )
        else:
            await db.execute(
                "INSERT INTO notes (number, title, file_path, file_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (number, title, file_path, file_id, now, now),
            )
        await db.commit()


async def delete_note(number: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM notes WHERE number = ?", (number,))
        row = await cur.fetchone()
        if not row:
            return None
        await db.execute("DELETE FROM notes WHERE number = ?", (number,))
        await db.commit()
        return dict(row)


async def list_notes() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT number, title FROM notes ORDER BY number")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
