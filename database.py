import aiosqlite
from datetime import datetime
from typing import Optional
from config import DB_PATH


async def init_db() -> None:
    """Создаёт таблицы, если их ещё нет."""
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


# ---------- students ----------

async def add_student(telegram_id: Optional[int] = None,
                      username: Optional[str] = None) -> str:
    """
    Возвращает строку-статус: 'added', 'exists', 'invalid'.
    Принимает либо telegram_id, либо username (без @).
    """
    if telegram_id is None and not username:
        return "invalid"

    username = username.lstrip("@").lower() if username else None
    now = datetime.utcnow().isoformat(timespec="seconds")

    async with aiosqlite.connect(DB_PATH) as db:
        # проверим, есть ли уже
        if telegram_id is not None:
            cur = await db.execute(
                "SELECT id FROM students WHERE telegram_id = ?", (telegram_id,)
            )
            if await cur.fetchone():
                return "exists"
        if username:
            cur = await db.execute(
                "SELECT id FROM students WHERE username = ?", (username,)
            )
            if await cur.fetchone():
                return "exists"

        try:
            await db.execute(
                "INSERT INTO students (telegram_id, username, added_at) VALUES (?, ?, ?)",
                (telegram_id, username, now),
            )
            await db.commit()
            return "added"
        except aiosqlite.IntegrityError:
            return "exists"


async def remove_student(telegram_id: Optional[int] = None,
                         username: Optional[str] = None) -> bool:
    if telegram_id is None and not username:
        return False
    username = username.lstrip("@").lower() if username else None

    async with aiosqlite.connect(DB_PATH) as db:
        if telegram_id is not None:
            cur = await db.execute(
                "DELETE FROM students WHERE telegram_id = ?", (telegram_id,)
            )
        else:
            cur = await db.execute(
                "DELETE FROM students WHERE username = ?", (username,)
            )
        await db.commit()
        return cur.rowcount > 0


async def is_student(telegram_id: int, username: Optional[str] = None) -> bool:
    """Проверяет, является ли пользователь учеником (по id или username)."""
    username_clean = username.lstrip("@").lower() if username else None
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, telegram_id FROM students WHERE telegram_id = ? OR (username IS NOT NULL AND username = ?)",
            (telegram_id, username_clean),
        )
        row = await cur.fetchone()
        if not row:
            return False

        # Если ученик был добавлен по @username, привяжем сразу его telegram_id,
        # чтобы дальше работало даже после смены username.
        student_id, stored_tg_id = row
        if stored_tg_id is None and telegram_id:
            await db.execute(
                "UPDATE students SET telegram_id = ? WHERE id = ?",
                (telegram_id, student_id),
            )
            await db.commit()
        return True


async def list_students() -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT telegram_id, username, added_at FROM students ORDER BY added_at"
        )
        return await cur.fetchall()


# ---------- notes ----------

async def get_note(number: int) -> Optional[tuple]:
    """Возвращает (number, title, file_path, file_id) или None."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT number, title, file_path, file_id FROM notes WHERE number = ?",
            (number,),
        )
        return await cur.fetchone()


async def upsert_note(number: int, title: str, file_path: str,
                      file_id: Optional[str]) -> str:
    """
    Создаёт или заменяет конспект.
    Возвращает 'added' или 'updated'.
    """
    now = datetime.utcnow().isoformat(timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM notes WHERE number = ?", (number,))
        exists = await cur.fetchone()
        if exists:
            await db.execute(
                """UPDATE notes
                   SET title = ?, file_path = ?, file_id = ?, updated_at = ?
                   WHERE number = ?""",
                (title, file_path, file_id, now, number),
            )
            await db.commit()
            return "updated"
        else:
            await db.execute(
                """INSERT INTO notes (number, title, file_path, file_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (number, title, file_path, file_id, now, now),
            )
            await db.commit()
            return "added"


async def delete_note(number: int) -> Optional[str]:
    """Удаляет запись о конспекте. Возвращает путь к файлу или None."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT file_path FROM notes WHERE number = ?", (number,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        await db.execute("DELETE FROM notes WHERE number = ?", (number,))
        await db.commit()
        return row[0]


async def list_notes() -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT number, title FROM notes ORDER BY number"
        )
        return await cur.fetchall()
