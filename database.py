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
            value TEXT UNIQUE NOT NULL,
            added_at TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number INTEGER UNIQUE NOT NULL,
            title TEXT NOT NULL,
            file_path TEXT,
            file_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        conn.commit()


def add_student(value: str):
    value = value.strip().lower()
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO students (value, added_at) VALUES (?, ?)",
            (value, now)
        )
        conn.commit()


def remove_student(value: str):
    value = value.strip().lower()

    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM students WHERE value = ?", (value,))
        conn.commit()
        return cursor.rowcount


def get_students():
    with get_connection() as conn:
        return conn.execute(
            "SELECT value, added_at FROM students ORDER BY id DESC"
        ).fetchall()


def is_student_allowed(telegram_id: int, username: str | None):
    values = [str(telegram_id)]

    if username:
        values.append("@" + username.lower())

    with get_connection() as conn:
        cursor = conn.execute(
            f"SELECT id FROM students WHERE value IN ({','.join(['?'] * len(values))})",
            values
        )
        return cursor.fetchone() is not None


def get_note(number: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT number, title, file_path, file_id FROM notes WHERE number = ?",
            (number,)
        ).fetchone()


def get_notes():
    with get_connection() as conn:
        return conn.execute(
            "SELECT number, title, created_at, updated_at FROM notes ORDER BY number ASC"
        ).fetchall()


def note_exists(number: int):
    return get_note(number) is not None


def save_note(number: int, title: str, file_path: str | None, file_id: str):
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection() as conn:
        existing = get_note(number)

        if existing:
            conn.execute("""
            UPDATE notes
            SET title = ?, file_path = ?, file_id = ?, updated_at = ?
            WHERE number = ?
            """, (title, file_path, file_id, now, number))
        else:
            conn.execute("""
            INSERT INTO notes (number, title, file_path, file_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (number, title, file_path, file_id, now, now))

        conn.commit()


def delete_note(number: int):
    note = get_note(number)

    with get_connection() as conn:
        conn.execute("DELETE FROM notes WHERE number = ?", (number,))
        conn.commit()

    return note
