import sqlite3
import os

DB_PATH = os.getenv(“DB_PATH”, “notes_bot.db”)

class Database:
def **init**(self):
self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
self._create_tables()

```
def _create_tables(self):
    self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY,
            user_id     INTEGER UNIQUE,
            username    TEXT,
            first_name  TEXT,
            added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS notes (
            id          INTEGER PRIMARY KEY,
            note_number INTEGER UNIQUE,
            title       TEXT NOT NULL,
            file_id     TEXT NOT NULL,
            added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    self.conn.commit()

# ─── Users ───────────────────────────────────────────────────────────────

def user_exists(self, user_id: int) -> bool:
    cur = self.conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    return cur.fetchone() is not None

def add_user_by_id(self, user_id: int, username: str = None, first_name: str = None) -> bool:
    """Returns True if added, False if already exists."""
    try:
        self.conn.execute(
            "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name)
        )
        self.conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def add_user_by_username(self, username: str) -> bool:
    """Add user by username (without @). Returns True if added."""
    try:
        self.conn.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?)",
            (None, username)
        )
        self.conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def update_user_info(self, user_id: int, username: str, first_name: str):
    """Update user info when they interact with the bot."""
    existing = self.conn.execute(
        "SELECT id FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()

    if existing:
        self.conn.execute(
            "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
            (username, first_name, user_id)
        )
    elif username:
        # Link username record to real user_id
        self.conn.execute(
            "UPDATE users SET user_id = ?, first_name = ? WHERE username = ? AND user_id IS NULL",
            (user_id, first_name, username)
        )
    self.conn.commit()

def remove_user_by_id(self, user_id: int) -> bool:
    cur = self.conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    self.conn.commit()
    return cur.rowcount > 0

def remove_user_by_username(self, username: str) -> bool:
    cur = self.conn.execute("DELETE FROM users WHERE username = ?", (username,))
    self.conn.commit()
    return cur.rowcount > 0

def get_all_users(self):
    cur = self.conn.execute(
        "SELECT user_id, username, first_name FROM users ORDER BY added_at DESC"
    )
    return cur.fetchall()

# ─── Notes ───────────────────────────────────────────────────────────────

def get_note(self, note_number: int):
    cur = self.conn.execute(
        "SELECT note_number, title, file_id FROM notes WHERE note_number = ?",
        (note_number,)
    )
    return cur.fetchone()

def get_all_notes(self):
    cur = self.conn.execute(
        "SELECT note_number, title FROM notes ORDER BY note_number ASC"
    )
    return cur.fetchall()

def add_note(self, note_number: int, title: str, file_id: str) -> bool:
    try:
        self.conn.execute(
            "INSERT INTO notes (note_number, title, file_id) VALUES (?, ?, ?)",
            (note_number, title, file_id)
        )
        self.conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def update_note(self, note_number: int, title: str, file_id: str):
    self.conn.execute(
        "UPDATE notes SET title = ?, file_id = ? WHERE note_number = ?",
        (title, file_id, note_number)
    )
    self.conn.commit()

def delete_note(self, note_number: int) -> bool:
    cur = self.conn.execute("DELETE FROM notes WHERE note_number = ?", (note_number,))
    self.conn.commit()
    return cur.rowcount > 0
```
