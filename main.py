import asyncio
import json
import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, FSInputFile
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

BASE_DIR = Path(__file__).resolve().parent
NOTES_DIR = BASE_DIR / "notes"
INDEX_FILE = NOTES_DIR / "index.json"
DB_FILE = BASE_DIR / "bot.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("conspect-bot")


def init_db() -> None:
    with sqlite3.connect(DB_FILE) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                note_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.commit()


def load_notes_index() -> dict:
    if not INDEX_FILE.exists():
        return {}
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {str(k): v for k, v in data.items()}
    except Exception:
        logger.exception("Cannot read notes/index.json")
        return {}


def save_notes_index(index: dict) -> None:
    NOTES_DIR.mkdir(exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def normalize_username(username: str | None) -> str | None:
    if not username:
        return None
    username = username.strip()
    username = username[1:] if username.startswith("@") else username
    return username.lower() if username else None


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_allowed(user_id: int, username: str | None) -> bool:
    if is_admin(user_id):
        return True
    norm_username = normalize_username(username)
    with sqlite3.connect(DB_FILE) as db:
        row = db.execute(
            """
            SELECT 1 FROM students
            WHERE telegram_id = ? OR username = ?
            LIMIT 1
            """,
            (user_id, norm_username),
        ).fetchone()
    return row is not None


def add_student(value: str) -> tuple[bool, str]:
    value = value.strip()
    if not value:
        return False, "ÐÑÑÑÐ¾Ðµ Ð·Ð½Ð°ÑÐµÐ½Ð¸Ðµ."

    tg_id = int(value) if value.isdigit() else None
    username = normalize_username(value) if not value.isdigit() else None

    try:
        with sqlite3.connect(DB_FILE) as db:
            db.execute(
                "INSERT OR IGNORE INTO students (telegram_id, username) VALUES (?, ?)",
                (tg_id, username),
            )
            db.commit()
        shown = str(tg_id) if tg_id else f"@{username}"
        return True, shown
    except sqlite3.IntegrityError:
        shown = str(tg_id) if tg_id else f"@{username}"
        return False, shown


def remove_student(value: str) -> bool:
    value = value.strip()
    tg_id = int(value) if value.isdigit() else None
    username = normalize_username(value) if not value.isdigit() else None
    with sqlite3.connect(DB_FILE) as db:
        cur = db.execute(
            "DELETE FROM students WHERE telegram_id = ? OR username = ?",
            (tg_id, username),
        )
        db.commit()
        return cur.rowcount > 0


def parse_students(text: str) -> list[str]:
    # ÐÐµÑÑÑ ID Ð¸ @username Ð¸Ð· Ð»ÑÐ±Ð¾Ð³Ð¾ ÑÐµÐºÑÑÐ°, Ð²ÐºÐ»ÑÑÐ°Ñ ÑÐ¿Ð¸ÑÐ¾Ðº ÑÐµÑÐµÐ· Ð¿ÑÐ¾Ð±ÐµÐ», Ð¿ÐµÑÐµÐ½Ð¾ÑÑ, Ð·Ð°Ð¿ÑÑÑÐµ
    values = re.findall(r"@\w+|\b\d{5,}\b", text)
    return values


def log_sent(user_id: int, note_number: str) -> None:
    with sqlite3.connect(DB_FILE) as db:
        db.execute(
            "INSERT INTO sent_logs (telegram_id, note_number) VALUES (?, ?)",
            (user_id, note_number),
        )
        db.commit()


async def send_note(message: Message, number: str) -> None:
    index = load_notes_index()
    note = index.get(number)

    if not note:
        await message.answer(
            f"â ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ â{number} Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½.\n\n"
            "ÐÑÐ¾Ð²ÐµÑÑ Ð½Ð¾Ð¼ÐµÑ Ð¸Ð»Ð¸ Ð¿Ð¾Ð¿ÑÐ¾ÑÐ¸ Ð°Ð´Ð¼Ð¸Ð½Ð° Ð´Ð¾Ð±Ð°Ð²Ð¸ÑÑ ÑÑÐ¾Ñ PDF."
        )
        return

    topic = note.get("topic", "ÐÐµÐ· Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ñ")
    filename = note.get("file", f"{number}.pdf")
    pdf_path = NOTES_DIR / filename

    if not pdf_path.exists():
        await message.answer(
            f"â ï¸ Ð¢ÐµÐ¼Ð° Ð½Ð°Ð¹Ð´ÐµÐ½Ð°, Ð½Ð¾ PDF-ÑÐ°Ð¹Ð» Ð¾ÑÑÑÑÑÑÐ²ÑÐµÑ.\n\n"
            f"ð â{number}\n"
            f"ð Ð¢ÐµÐ¼Ð°: {topic}\n"
            f"ð ÐÐ¶Ð¸Ð´Ð°Ð»ÑÑ ÑÐ°Ð¹Ð»: notes/{filename}"
        )
        return

    caption = (
        f"ð <b>ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ â{number}</b>\n"
        f"ð <b>Ð¢ÐµÐ¼Ð°:</b> {topic}"
    )
    await message.answer_document(FSInputFile(pdf_path), caption=caption)
    log_sent(message.from_user.id, number)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty. Add BOT_TOKEN in Railway Variables.")

    init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        if not is_allowed(message.from_user.id, message.from_user.username):
            await message.answer(
                "â Ð£ Ð²Ð°Ñ Ð¿Ð¾ÐºÐ° Ð½ÐµÑ Ð´Ð¾ÑÑÑÐ¿Ð° Ðº ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ°Ð¼.\n\n"
                "ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð°Ð´Ð¼Ð¸Ð½Ð¸ÑÑÑÐ°ÑÐ¾ÑÑ Ð²Ð°Ñ ID:\n"
                f"<code>{message.from_user.id}</code>"
            )
            return

        await message.answer(
            "â ÐÐ¾ÑÑÑÐ¿ Ð¾ÑÐºÑÑÑ.\n\n"
            "ÐÐ°Ð¿Ð¸ÑÐ¸ÑÐµ Ð½Ð¾Ð¼ÐµÑ ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ°, Ð½Ð°Ð¿ÑÐ¸Ð¼ÐµÑ: <b>29</b>\n"
            "Ð Ñ Ð¾ÑÐ¿ÑÐ°Ð²Ð»Ñ PDF-ÑÐ°Ð¹Ð» Ñ ÑÐµÐ¼Ð¾Ð¹."
        )

    @dp.message(Command("id"))
    async def my_id(message: Message) -> None:
        await message.answer(
            f"ÐÐ°Ñ Telegram ID:\n<code>{message.from_user.id}</code>\n\n"
            f"Username: @{message.from_user.username}" if message.from_user.username else
            f"ÐÐ°Ñ Telegram ID:\n<code>{message.from_user.id}</code>"
        )

    @dp.message(Command("help"))
    async def help_cmd(message: Message) -> None:
        text = (
            "ð <b>ÐÐ°Ðº Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÑÑÑ:</b>\n"
            "1) ÐÐ°Ð¿Ð¸ÑÐ¸ÑÐµ Ð½Ð¾Ð¼ÐµÑ ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ°: <b>29</b>\n"
            "2) ÐÐ¾Ñ Ð¾ÑÐ¿ÑÐ°Ð²Ð¸Ñ PDF Ð¸ ÑÐµÐ¼Ñ.\n\n"
            "ð <b>ÐÐ¾Ð¼Ð°Ð½Ð´Ñ Ð°Ð´Ð¼Ð¸Ð½Ð°:</b>\n"
            "<code>/add 123456789</code>\n"
            "<code>/add @username</code>\n"
            "<code>/add @user1 @user2 123456789</code>\n"
            "<code>/remove @username</code>\n"
            "<code>/students</code>\n"
            "<code>/notes</code>\n"
            "<code>/setnote 29 | Ð¢ÐµÐ¼Ð° ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ° | 29.pdf</code>"
        )
        await message.answer(text)

    @dp.message(Command("add"))
    async def add_cmd(message: Message) -> None:
        if not is_admin(message.from_user.id):
            return await message.answer("â ÐÐ¾Ð¼Ð°Ð½Ð´Ð° ÑÐ¾Ð»ÑÐºÐ¾ Ð´Ð»Ñ Ð°Ð´Ð¼Ð¸Ð½Ð°.")

        values = parse_students(message.text or "")
        if not values:
            return await message.answer(
                "ÐÐ°Ð¿Ð¸ÑÐ¸ ÑÐ°Ðº:\n"
                "<code>/add @username</code>\n"
                "Ð¸Ð»Ð¸ Ð¼Ð°ÑÑÐ¾Ð²Ð¾:\n"
                "<code>/add @user1 @user2 123456789</code>"
            )

        added = []
        for value in values:
            ok, shown = add_student(value)
            added.append(shown)

        await message.answer(
            "â ÐÐ¾ÑÑÑÐ¿ Ð²ÑÐ´Ð°Ð½:\n" + "\n".join(f"â¢ {x}" for x in added)
        )

    @dp.message(Command("remove"))
    async def remove_cmd(message: Message) -> None:
        if not is_admin(message.from_user.id):
            return await message.answer("â ÐÐ¾Ð¼Ð°Ð½Ð´Ð° ÑÐ¾Ð»ÑÐºÐ¾ Ð´Ð»Ñ Ð°Ð´Ð¼Ð¸Ð½Ð°.")

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            return await message.answer("ÐÑÐ¸Ð¼ÐµÑ: <code>/remove @username</code>")

        ok = remove_student(parts[1])
        await message.answer("â Ð£Ð´Ð°Ð»ÑÐ½ Ð¸Ð· Ð´Ð¾ÑÑÑÐ¿Ð°." if ok else "ÐÐµ Ð½Ð°Ð¹Ð´ÐµÐ½ Ð² Ð±Ð°Ð·Ðµ.")

    @dp.message(Command("students"))
    async def students_cmd(message: Message) -> None:
        if not is_admin(message.from_user.id):
            return await message.answer("â ÐÐ¾Ð¼Ð°Ð½Ð´Ð° ÑÐ¾Ð»ÑÐºÐ¾ Ð´Ð»Ñ Ð°Ð´Ð¼Ð¸Ð½Ð°.")

        with sqlite3.connect(DB_FILE) as db:
            rows = db.execute(
                "SELECT telegram_id, username, created_at FROM students ORDER BY id DESC LIMIT 200"
            ).fetchall()

        if not rows:
            return await message.answer("Ð¡Ð¿Ð¸ÑÐ¾Ðº ÑÑÐµÐ½Ð¸ÐºÐ¾Ð² Ð¿Ð¾ÐºÐ° Ð¿ÑÑÑ.")

        lines = []
        for tg_id, username, created_at in rows:
            who = str(tg_id) if tg_id else f"@{username}"
            lines.append(f"â¢ {who} â {created_at}")
        await message.answer("ð¥ <b>Ð£ÑÐµÐ½Ð¸ÐºÐ¸:</b>\n" + "\n".join(lines))

    @dp.message(Command("notes"))
    async def notes_cmd(message: Message) -> None:
        if not is_allowed(message.from_user.id, message.from_user.username):
            return await message.answer("â ÐÐµÑ Ð´Ð¾ÑÑÑÐ¿Ð°.")

        index = load_notes_index()
        if not index:
            return await message.answer("ÐÐ¾Ð½ÑÐ¿ÐµÐºÑÑ Ð¿Ð¾ÐºÐ° Ð½Ðµ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ñ.")

        lines = []
        for number in sorted(index.keys(), key=lambda x: int(x) if x.isdigit() else 999999):
            topic = index[number].get("topic", "ÐÐµÐ· Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ñ")
            lines.append(f"â{number} â {topic}")

        text = "ð <b>Ð¡Ð¿Ð¸ÑÐ¾Ðº ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ¾Ð²:</b>\n" + "\n".join(lines[:100])
        await message.answer(text)

    @dp.message(Command("setnote"))
    async def setnote_cmd(message: Message) -> None:
        if not is_admin(message.from_user.id):
            return await message.answer("â ÐÐ¾Ð¼Ð°Ð½Ð´Ð° ÑÐ¾Ð»ÑÐºÐ¾ Ð´Ð»Ñ Ð°Ð´Ð¼Ð¸Ð½Ð°.")

        raw = (message.text or "").replace("/setnote", "", 1).strip()
        parts = [x.strip() for x in raw.split("|")]
        if len(parts) != 3:
            return await message.answer(
                "Ð¤Ð¾ÑÐ¼Ð°Ñ:\n"
                "<code>/setnote 29 | Ð¢ÐµÐ¼Ð° ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ° | 29.pdf</code>"
            )

        number, topic, filename = parts
        if not number:
            return await message.answer("Ð£ÐºÐ°Ð¶Ð¸ Ð½Ð¾Ð¼ÐµÑ ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ°.")

        index = load_notes_index()
        index[str(number)] = {"topic": topic, "file": filename}
        save_notes_index(index)
        await message.answer(
            f"â ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ ÑÐ¾ÑÑÐ°Ð½ÑÐ½ Ð² Ð±Ð°Ð·Ðµ:\n"
            f"â{number} â {topic}\n"
            f"Ð¤Ð°Ð¹Ð»: notes/{filename}"
        )


    @dp.message(Command("delnote"))
    async def delnote_cmd(message: Message) -> None:
        if not is_admin(message.from_user.id):
            return await message.answer("â ÐÐ¾Ð¼Ð°Ð½Ð´Ð° ÑÐ¾Ð»ÑÐºÐ¾ Ð´Ð»Ñ Ð°Ð´Ð¼Ð¸Ð½Ð°.")

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            return await message.answer("Ð¤Ð¾ÑÐ¼Ð°Ñ: <code>/delnote 29</code>")

        number = parts[1].strip()
        index = load_notes_index()
        note = index.get(number)
        if not note:
            return await message.answer(f"â ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ â{number} Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½.")

        filename = note.get("file", f"{number}.pdf")
        pdf_path = NOTES_DIR / filename
        if pdf_path.exists():
            pdf_path.unlink()

        del index[number]
        save_notes_index(index)
        await message.answer(f"ð ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ â{number} ÑÐ´Ð°Ð»ÑÐ½ Ð¸Ð· Ð±Ð°Ð·Ñ Ð¸ PDF ÑÐ´Ð°Ð»ÑÐ½ Ñ ÑÐµÑÐ²ÐµÑÐ°.")

    @dp.message(Command("replace"))
    async def replace_cmd(message: Message) -> None:
        if not is_admin(message.from_user.id):
            return await message.answer("â ÐÐ¾Ð¼Ð°Ð½Ð´Ð° ÑÐ¾Ð»ÑÐºÐ¾ Ð´Ð»Ñ Ð°Ð´Ð¼Ð¸Ð½Ð°.")

        if not message.document:
            return await message.answer(
                "Ð§ÑÐ¾Ð±Ñ Ð·Ð°Ð¼ÐµÐ½Ð¸ÑÑ ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑ, Ð¾ÑÐ¿ÑÐ°Ð²Ñ PDF Ð¾Ð´Ð½Ð¸Ð¼ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸ÐµÐ¼ Ñ Ð¿Ð¾Ð´Ð¿Ð¸ÑÑÑ:\n"
                "<code>/replace 29 | ÐÐ¾Ð²Ð°Ñ ÑÐµÐ¼Ð°</code>"
            )

        doc = message.document
        if not doc.file_name.lower().endswith(".pdf"):
            return await message.answer("ÐÐ»Ñ Ð·Ð°Ð¼ÐµÐ½Ñ Ð½ÑÐ¶ÐµÐ½ PDF-ÑÐ°Ð¹Ð».")

        raw = (message.caption or message.text or "").replace("/replace", "", 1).strip()
        parts = [x.strip() for x in raw.split("|", 1)]
        if len(parts) != 2 or not parts[0]:
            return await message.answer(
                "Ð¤Ð¾ÑÐ¼Ð°Ñ Ð¿Ð¾Ð´Ð¿Ð¸ÑÐ¸ Ðº PDF:\n"
                "<code>/replace 29 | ÐÐ¾Ð²Ð°Ñ ÑÐµÐ¼Ð°</code>"
            )

        number, topic = parts
        filename = f"{number}.pdf"
        NOTES_DIR.mkdir(exist_ok=True)

        file = await bot.get_file(doc.file_id)
        await bot.download_file(file.file_path, destination=NOTES_DIR / filename)

        index = load_notes_index()
        index[str(number)] = {"topic": topic, "file": filename}
        save_notes_index(index)

        await message.answer(
            f"â»ï¸ ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ Ð·Ð°Ð¼ÐµÐ½ÑÐ½:\n"
            f"ð â{number}\n"
            f"ð {topic}\n"
            f"ð notes/{filename}"
        )

    @dp.message(F.document)
    async def upload_pdf(message: Message) -> None:
        if not is_admin(message.from_user.id):
            return await message.answer("â ÐÐ°Ð³ÑÑÐ¶Ð°ÑÑ PDF Ð¼Ð¾Ð¶ÐµÑ ÑÐ¾Ð»ÑÐºÐ¾ Ð°Ð´Ð¼Ð¸Ð½.")

        doc = message.document
        if not doc.file_name.lower().endswith(".pdf"):
            return await message.answer("ÐÑÐ¿ÑÐ°Ð²Ñ Ð¸Ð¼ÐµÐ½Ð½Ð¾ PDF-ÑÐ°Ð¹Ð».")

        # ÐÐ¾Ð´Ð´ÐµÑÐ¶ÐºÐ° Ð¿Ð¾Ð´Ð¿Ð¸ÑÐ¸ Ðº ÑÐ°Ð¹Ð»Ñ:
        # 29 | Ð¢ÐµÐ¼Ð° ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ°
        caption = (message.caption or "").strip()
        if "|" not in caption:
            return await message.answer(
                "PDF Ð¿Ð¾Ð»ÑÑÐµÐ½, Ð½Ð¾ Ð½ÑÐ¶Ð½Ð° Ð¿Ð¾Ð´Ð¿Ð¸ÑÑ Ð² ÑÐ¾ÑÐ¼Ð°ÑÐµ:\n"
                "<code>29 | Ð¢ÐµÐ¼Ð° ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ°</code>"
            )

        number, topic = [x.strip() for x in caption.split("|", 1)]
        filename = f"{number}.pdf"
        NOTES_DIR.mkdir(exist_ok=True)

        file = await bot.get_file(doc.file_id)
        await bot.download_file(file.file_path, destination=NOTES_DIR / filename)

        index = load_notes_index()
        index[str(number)] = {"topic": topic, "file": filename}
        save_notes_index(index)

        await message.answer(
            f"â PDF Ð·Ð°Ð³ÑÑÐ¶ÐµÐ½ Ð¸ ÑÐ¾ÑÑÐ°Ð½ÑÐ½. ÐÑÐ»Ð¸ ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑ Ñ ÑÐ°ÐºÐ¸Ð¼ Ð½Ð¾Ð¼ÐµÑÐ¾Ð¼ ÑÐ¶Ðµ Ð±ÑÐ» â Ð¾Ð½ Ð·Ð°Ð¼ÐµÐ½ÑÐ½:\n"
            f"ð â{number}\n"
            f"ð {topic}\n"
            f"ð notes/{filename}"
        )

    @dp.message()
    async def text_handler(message: Message) -> None:
        if not is_allowed(message.from_user.id, message.from_user.username):
            return await message.answer(
                "â Ð£ Ð²Ð°Ñ Ð½ÐµÑ Ð´Ð¾ÑÑÑÐ¿Ð°.\n\n"
                "ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð°Ð´Ð¼Ð¸Ð½Ð¸ÑÑÑÐ°ÑÐ¾ÑÑ Ð²Ð°Ñ ID:\n"
                f"<code>{message.from_user.id}</code>"
            )

        text = (message.text or "").strip()
        if text.isdigit():
            return await send_note(message, text)

        await message.answer(
            "ÐÐ°Ð¿Ð¸ÑÐ¸ÑÐµ ÑÐ¾Ð»ÑÐºÐ¾ Ð½Ð¾Ð¼ÐµÑ ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ°, Ð½Ð°Ð¿ÑÐ¸Ð¼ÐµÑ: <b>29</b>\n"
            "Ð¡Ð¿Ð¸ÑÐ¾Ðº ÑÐµÐ¼: /notes"
        )

    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
