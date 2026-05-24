import aiosqlite
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                role TEXT DEFAULT 'user',
                has_access INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS curators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                curator_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (curator_id) REFERENCES curators(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                curator_id INTEGER,
                group_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (curator_id) REFERENCES curators(id),
                FOREIGN KEY (group_id) REFERENCES groups(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS workbooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial_number INTEGER UNIQUE NOT NULL,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS checklists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial_number INTEGER UNIQUE NOT NULL,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by_admin_id INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                curator_id INTEGER NOT NULL,
                group_id INTEGER,
                pdf_path TEXT,
                student_full_name TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'received',
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (curator_id) REFERENCES curators(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS submission_photos_buffer (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_telegram_id INTEGER NOT NULL,
                photo_path TEXT NOT NULL,
                order_index INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS exam_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                curator_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                slot_time TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 15,
                google_meet_link TEXT,
                is_booked INTEGER DEFAULT 0,
                booked_by_student_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (curator_id) REFERENCES curators(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS exam_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                curator_id INTEGER NOT NULL,
                group_id INTEGER,
                student_full_name TEXT,
                booking_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                google_meet_link TEXT,
                status TEXT DEFAULT 'booked',
                notified_10_min INTEGER DEFAULT 0,
                notified_start INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (slot_id) REFERENCES exam_slots(id),
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (curator_id) REFERENCES curators(id)
            )
        """)

        await db.commit()
        logger.info("Database initialized successfully")


# ââ USERS ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def get_or_create_user(telegram_id: int, username: str | None, full_name: str) -> dict:
    async with await get_db() as db:
        row = await db.execute_fetchall(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        if row:
            await db.execute(
                "UPDATE users SET username=?, full_name=? WHERE telegram_id=?",
                (username, full_name, telegram_id)
            )
            await db.commit()
            row = await db.execute_fetchall("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
            return dict(row[0])
        await db.execute(
            "INSERT INTO users (telegram_id, username, full_name) VALUES (?,?,?)",
            (telegram_id, username, full_name)
        )
        await db.commit()
        row = await db.execute_fetchall("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        return dict(row[0])


async def get_user(telegram_id: int) -> dict | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        return dict(rows[0]) if rows else None


async def set_user_access(telegram_id: int, has_access: bool):
    async with await get_db() as db:
        await db.execute(
            "UPDATE users SET has_access=? WHERE telegram_id=?",
            (1 if has_access else 0, telegram_id)
        )
        await db.commit()


async def set_user_role(telegram_id: int, role: str):
    async with await get_db() as db:
        await db.execute("UPDATE users SET role=? WHERE telegram_id=?", (role, telegram_id))
        await db.commit()


async def get_all_users_with_access() -> list[dict]:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM users WHERE has_access=1")
        return [dict(r) for r in rows]


# ââ CURATORS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def add_curator(telegram_id: int, username: str | None, full_name: str) -> dict:
    async with await get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO curators (telegram_id, username, full_name) VALUES (?,?,?)",
            (telegram_id, username, full_name)
        )
        await db.execute(
            "UPDATE curators SET username=?, full_name=? WHERE telegram_id=?",
            (username, full_name, telegram_id)
        )
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, full_name, role) VALUES (?,?,?,'curator')",
            (telegram_id, username, full_name)
        )
        await db.execute(
            "UPDATE users SET role='curator', has_access=1 WHERE telegram_id=?", (telegram_id,)
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM curators WHERE telegram_id=?", (telegram_id,))
        return dict(rows[0])


async def get_curator_by_telegram_id(telegram_id: int) -> dict | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM curators WHERE telegram_id=?", (telegram_id,))
        return dict(rows[0]) if rows else None


async def get_curator_by_id(curator_id: int) -> dict | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM curators WHERE id=?", (curator_id,))
        return dict(rows[0]) if rows else None


async def get_all_curators() -> list[dict]:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM curators ORDER BY full_name")
        return [dict(r) for r in rows]


async def remove_curator(telegram_id: int):
    async with await get_db() as db:
        await db.execute("DELETE FROM curators WHERE telegram_id=?", (telegram_id,))
        await db.execute("UPDATE users SET role='user' WHERE telegram_id=?", (telegram_id,))
        await db.commit()


# ââ GROUPS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def add_group(title: str, curator_id: int) -> dict:
    async with await get_db() as db:
        cursor = await db.execute(
            "INSERT INTO groups (title, curator_id) VALUES (?,?)", (title, curator_id)
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM groups WHERE id=?", (cursor.lastrowid,))
        return dict(rows[0])


async def get_groups_by_curator(curator_id: int) -> list[dict]:
    async with await get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM groups WHERE curator_id=? ORDER BY title", (curator_id,)
        )
        return [dict(r) for r in rows]


async def get_group_by_id(group_id: int) -> dict | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM groups WHERE id=?", (group_id,))
        return dict(rows[0]) if rows else None


async def get_all_groups() -> list[dict]:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM groups ORDER BY title")
        return [dict(r) for r in rows]


async def delete_group(group_id: int):
    async with await get_db() as db:
        await db.execute("DELETE FROM groups WHERE id=?", (group_id,))
        await db.commit()


# ââ STUDENTS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def add_student(telegram_id: int, username: str | None, full_name: str,
                      curator_id: int, group_id: int | None) -> dict:
    async with await get_db() as db:
        await db.execute(
            """INSERT OR IGNORE INTO students (telegram_id, username, full_name, curator_id, group_id)
               VALUES (?,?,?,?,?)""",
            (telegram_id, username, full_name, curator_id, group_id)
        )
        await db.execute(
            """UPDATE students SET username=?, full_name=?, curator_id=?, group_id=?
               WHERE telegram_id=?""",
            (username, full_name, curator_id, group_id, telegram_id)
        )
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, full_name, role, has_access) VALUES (?,?,?,'student',1)",
            (telegram_id, username, full_name)
        )
        await db.execute(
            "UPDATE users SET role='student', has_access=1 WHERE telegram_id=?", (telegram_id,)
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM students WHERE telegram_id=?", (telegram_id,))
        return dict(rows[0])


async def get_student_by_telegram_id(telegram_id: int) -> dict | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM students WHERE telegram_id=?", (telegram_id,))
        return dict(rows[0]) if rows else None


async def get_students_by_curator(curator_id: int) -> list[dict]:
    async with await get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM students WHERE curator_id=? ORDER BY full_name", (curator_id,)
        )
        return [dict(r) for r in rows]


async def get_students_by_group(group_id: int) -> list[dict]:
    async with await get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM students WHERE group_id=? ORDER BY full_name", (group_id,)
        )
        return [dict(r) for r in rows]


async def remove_student(telegram_id: int):
    async with await get_db() as db:
        await db.execute("DELETE FROM students WHERE telegram_id=?", (telegram_id,))
        await db.execute("UPDATE users SET role='user' WHERE telegram_id=?", (telegram_id,))
        await db.commit()


# ââ WORKBOOKS ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def add_workbook(title: str, file_path: str, added_by: int) -> dict:
    async with await get_db() as db:
        row = await db.execute_fetchall("SELECT MAX(serial_number) as mx FROM workbooks")
        max_sn = row[0]["mx"] or 0
        sn = max_sn + 1
        cursor = await db.execute(
            "INSERT INTO workbooks (serial_number, title, file_path, added_by) VALUES (?,?,?,?)",
            (sn, title, file_path, added_by)
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM workbooks WHERE id=?", (cursor.lastrowid,))
        return dict(rows[0])


async def get_all_workbooks() -> list[dict]:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM workbooks ORDER BY serial_number")
        return [dict(r) for r in rows]


async def get_workbook_by_serial(serial: int) -> dict | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM workbooks WHERE serial_number=?", (serial,))
        return dict(rows[0]) if rows else None


async def delete_workbook(serial: int) -> str | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT file_path FROM workbooks WHERE serial_number=?", (serial,))
        if not rows:
            return None
        fp = rows[0]["file_path"]
        await db.execute("DELETE FROM workbooks WHERE serial_number=?", (serial,))
        await db.commit()
        return fp


async def clear_all_workbooks() -> list[str]:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT file_path FROM workbooks")
        paths = [r["file_path"] for r in rows]
        await db.execute("DELETE FROM workbooks")
        await db.commit()
        return paths


# ââ CHECKLISTS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def add_checklist(title: str, file_path: str, file_type: str, added_by: int) -> dict:
    async with await get_db() as db:
        row = await db.execute_fetchall("SELECT MAX(serial_number) as mx FROM checklists")
        max_sn = row[0]["mx"] or 0
        sn = max_sn + 1
        cursor = await db.execute(
            "INSERT INTO checklists (serial_number, title, file_path, file_type, added_by_admin_id) VALUES (?,?,?,?,?)",
            (sn, title, file_path, file_type, added_by)
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM checklists WHERE id=?", (cursor.lastrowid,))
        return dict(rows[0])


async def get_all_checklists() -> list[dict]:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM checklists ORDER BY serial_number")
        return [dict(r) for r in rows]


async def get_checklist_by_serial(serial: int) -> dict | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM checklists WHERE serial_number=?", (serial,))
        return dict(rows[0]) if rows else None


async def delete_checklist(serial: int) -> str | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT file_path FROM checklists WHERE serial_number=?", (serial,))
        if not rows:
            return None
        fp = rows[0]["file_path"]
        await db.execute("DELETE FROM checklists WHERE serial_number=?", (serial,))
        await db.commit()
        return fp


async def clear_all_checklists() -> list[str]:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT file_path FROM checklists")
        paths = [r["file_path"] for r in rows]
        await db.execute("DELETE FROM checklists")
        await db.commit()
        return paths


# ââ SUBMISSIONS ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def create_submission(student_id: int, curator_id: int, group_id: int | None,
                            pdf_path: str, student_full_name: str) -> dict:
    async with await get_db() as db:
        cursor = await db.execute(
            """INSERT INTO submissions (student_id, curator_id, group_id, pdf_path, student_full_name)
               VALUES (?,?,?,?,?)""",
            (student_id, curator_id, group_id, pdf_path, student_full_name)
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM submissions WHERE id=?", (cursor.lastrowid,))
        return dict(rows[0])


async def get_submissions(curator_id: int | None = None, period: str = "all",
                          group_id: int | None = None, student_id: int | None = None) -> list[dict]:
    async with await get_db() as db:
        q = """
            SELECT s.*, st.username, st.telegram_id as student_telegram_id,
                   g.title as group_title, c.full_name as curator_name
            FROM submissions s
            LEFT JOIN students st ON s.student_id = st.id
            LEFT JOIN groups g ON s.group_id = g.id
            LEFT JOIN curators c ON s.curator_id = c.id
            WHERE 1=1
        """
        params: list = []
        if curator_id:
            q += " AND s.curator_id=?"
            params.append(curator_id)
        if group_id:
            q += " AND s.group_id=?"
            params.append(group_id)
        if student_id:
            q += " AND s.student_id=?"
            params.append(student_id)
        if period == "today":
            q += " AND DATE(s.submitted_at)=DATE('now')"
        elif period == "week":
            q += " AND s.submitted_at >= datetime('now', '-7 days')"
        elif period == "month":
            q += " AND s.submitted_at >= datetime('now', '-30 days')"
        q += " ORDER BY s.submitted_at DESC"
        rows = await db.execute_fetchall(q, params)
        return [dict(r) for r in rows]


async def clear_all_submissions() -> list[str]:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT pdf_path FROM submissions")
        paths = [r["pdf_path"] for r in rows if r["pdf_path"]]
        await db.execute("DELETE FROM submissions")
        await db.commit()
        return paths


# ââ PHOTO BUFFER âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def add_photo_to_buffer(student_telegram_id: int, photo_path: str, order_index: int):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO submission_photos_buffer (student_telegram_id, photo_path, order_index) VALUES (?,?,?)",
            (student_telegram_id, photo_path, order_index)
        )
        await db.commit()


async def get_buffer_photos(student_telegram_id: int) -> list[dict]:
    async with await get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM submission_photos_buffer WHERE student_telegram_id=? ORDER BY order_index",
            (student_telegram_id,)
        )
        return [dict(r) for r in rows]


async def clear_buffer(student_telegram_id: int):
    async with await get_db() as db:
        await db.execute(
            "DELETE FROM submission_photos_buffer WHERE student_telegram_id=?",
            (student_telegram_id,)
        )
        await db.commit()


async def count_buffer(student_telegram_id: int) -> int:
    async with await get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM submission_photos_buffer WHERE student_telegram_id=?",
            (student_telegram_id,)
        )
        return rows[0]["cnt"]


# ââ EXAM SLOTS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

async def add_exam_slots(curator_id: int, date: str, slots: list[str],
                         duration: int, meet_link: str) -> int:
    async with await get_db() as db:
        count = 0
        for slot_time in slots:
            await db.execute(
                """INSERT INTO exam_slots (curator_id, date, slot_time, duration_minutes, google_meet_link)
                   VALUES (?,?,?,?,?)""",
                (curator_id, date, slot_time, duration, meet_link)
            )
            count += 1
        await db.commit()
        return count


async def get_free_slots_for_curator(curator_id: int) -> list[dict]:
    async with await get_db() as db:
        rows = await db.execute_fetchall(
            """SELECT * FROM exam_slots WHERE curator_id=? AND is_booked=0
               AND date >= DATE('now') ORDER BY date, slot_time""",
            (curator_id,)
        )
        return [dict(r) for r in rows]


async def get_slot_by_id(slot_id: int) -> dict | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM exam_slots WHERE id=?", (slot_id,))
        return dict(rows[0]) if rows else None


async def book_slot(slot_id: int, student_id: int) -> bool:
    async with await get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT is_booked FROM exam_slots WHERE id=?", (slot_id,)
        )
        if not rows or rows[0]["is_booked"]:
            return False
        await db.execute(
            "UPDATE exam_slots SET is_booked=1, booked_by_student_id=? WHERE id=?",
            (student_id, slot_id)
        )
        await db.commit()
        return True


async def create_booking(slot_id: int, student_id: int, curator_id: int,
                         group_id: int | None, student_full_name: str,
                         meet_link: str) -> dict:
    async with await get_db() as db:
        cursor = await db.execute(
            """INSERT INTO exam_bookings
               (slot_id, student_id, curator_id, group_id, student_full_name, google_meet_link)
               VALUES (?,?,?,?,?,?)""",
            (slot_id, student_id, curator_id, group_id, student_full_name, meet_link)
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM exam_bookings WHERE id=?", (cursor.lastrowid,))
        return dict(rows[0])


async def get_student_active_booking(student_id: int) -> dict | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall(
            """SELECT b.*, s.date, s.slot_time, s.google_meet_link as slot_meet
               FROM exam_bookings b JOIN exam_slots s ON b.slot_id=s.id
               WHERE b.student_id=? AND b.status='booked'
               ORDER BY s.date, s.slot_time LIMIT 1""",
            (student_id,)
        )
        return dict(rows[0]) if rows else None


async def cancel_booking(booking_id: int) -> dict | None:
    async with await get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM exam_bookings WHERE id=?", (booking_id,))
        if not rows:
            return None
        b = dict(rows[0])
        await db.execute("UPDATE exam_bookings SET status='cancelled' WHERE id=?", (booking_id,))
        await db.execute("UPDATE exam_slots SET is_booked=0, booked_by_student_id=NULL WHERE id=?", (b["slot_id"],))
        await db.commit()
        return b


async def get_upcoming_bookings_for_notifications() -> list[dict]:
    async with await get_db() as db:
        rows = await db.execute_fetchall(
            """SELECT b.*, s.date, s.slot_time, s.google_meet_link as slot_meet,
                      st.telegram_id as student_telegram_id, st.username as student_username,
                      g.title as group_title, c.telegram_id as curator_telegram_id,
                      c.full_name as curator_name
               FROM exam_bookings b
               JOIN exam_slots s ON b.slot_id = s.id
               JOIN students st ON b.student_id = st.id
               LEFT JOIN groups g ON b.group_id = g.id
               JOIN curators c ON b.curator_id = c.id
               WHERE b.status='booked'"""
        )
        return [dict(r) for r in rows]


async def mark_notified(booking_id: int, kind: str):
    col = "notified_10_min" if kind == "10min" else "notified_start"
    async with await get_db() as db:
        await db.execute(f"UPDATE exam_bookings SET {col}=1 WHERE id=?", (booking_id,))
        await db.commit()


async def get_all_bookings(curator_id: int | None = None) -> list[dict]:
    async with await get_db() as db:
        q = """
            SELECT b.*, s.date, s.slot_time,
                   st.username as student_username, st.telegram_id as student_telegram_id,
                   g.title as group_title, c.full_name as curator_name
            FROM exam_bookings b
            JOIN exam_slots s ON b.slot_id=s.id
            JOIN students st ON b.student_id=st.id
            LEFT JOIN groups g ON b.group_id=g.id
            JOIN curators c ON b.curator_id=c.id
            WHERE 1=1
        """
        params = []
        if curator_id:
            q += " AND b.curator_id=?"
            params.append(curator_id)
        q += " ORDER BY s.date DESC, s.slot_time DESC"
        rows = await db.execute_fetchall(q, params)
        return [dict(r) for r in rows]
