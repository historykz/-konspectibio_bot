import sqlite3
from datetime import datetime
from config import DATABASE_PATH


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT UNIQUE,
            added_at TEXT NOT NULL
        )
        """)

        cursor.execute("""
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

        conn.commit()


def add_student(value: str):
    now = datetime.now().isoformat(timespec="seconds")

    telegram_id = None
    username = None

    value = value.strip()

    if value.startswith("@"):
        username = value[1:].lower()
    else:
        telegram_id = int(value)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT OR IGNORE INTO students (telegram_id, username, added_at)
        VALUES (?, ?, ?)
        """, (telegram_id, username, now))
        conn.commit()


def remove_student(value: str):
    value = value.strip()

    with get_connection() as conn:
        cursor = conn.cursor()

        if value.startswith("@"):
            username = value[1:].lower()
            cursor.execute("DELETE FROM students WHERE username = ?", (username,))
        else:
            telegram_id = int(value)
            cursor.execute("DELETE FROM students WHERE telegram_id = ?", (telegram_id,))

        conn.commit()
        return cursor.rowcount


def get_students():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT telegram_id, username, added_at
        FROM students
        ORDER BY id DESC
        """)
        return cursor.fetchall()


def is_student_allowed(telegram_id: int, username: str | None):
    username = username.lower() if username else None

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id FROM students
        WHERE telegram_id = ?
        OR username = ?
        """, (telegram_id, username))
        return cursor.fetchone() is not None


def get_note(number: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT number, title, file_path, file_id
        FROM notes
        WHERE number = ?
        """, (number,))
        return cursor.fetchone()


def get_notes():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT number, title, created_at, updated_at
        FROM notes
        ORDER BY number ASC
        """)
        return cursor.fetchall()


def note_exists(number: int):
    return get_note(number) is not None


def save_note(number: int, title: str, file_path: str, file_id: str):
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection() as conn:
        cursor = conn.cursor()

        existing = get_note(number)

        if existing:
            cursor.execute("""
            UPDATE notes
            SET title = ?, file_path = ?, file_id = ?, updated_at = ?
            WHERE number = ?
            """, (title, file_path, file_id, now, number))
        else:
            cursor.execute("""
            INSERT INTO notes (number, title, file_path, file_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (number, title, file_path, file_id, now, now))

        conn.commit()


def delete_note(number: int):
    note = get_note(number)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE number = ?", (number,))
        conn.commit()

    return note
