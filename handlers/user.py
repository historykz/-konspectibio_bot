import logging
import os

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile

import database as db
from utils import is_admin

logger = logging.getLogger(__name__)
router = Router(name="user")


WELCOME_STUDENT = (
    "Здравствуйте! 👋\n"
    "Введите номер конспекта, например: 29\n"
    "И я отправлю вам нужный PDF-файл."
)

WELCOME_ADMIN = (
    "Здравствуйте, администратор 👑\n"
    "Вы можете:\n"
    "📌 загрузить PDF-конспект\n"
    "📌 добавить ученика\n"
    "📌 удалить ученика\n"
    "📌 заменить конспект\n"
    "📌 посмотреть список конспектов\n\n"
    "Команды:\n"
    "/add_student, /add_students, /remove_student, /students\n"
    "/notes, /delete_note <номер>\n"
    "Чтобы добавить конспект — пришлите PDF файлом."
)

NO_ACCESS = "⛔ У вас нет доступа к конспектам. Обратитесь к администратору."


@router.message(CommandStart())
async def cmd_start(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(WELCOME_ADMIN)
        return
    if await db.is_student(message.from_user.id, message.from_user.username):
        await message.answer(WELCOME_STUDENT)
    else:
        await message.answer(NO_ACCESS)


@router.message(Command("list"))
async def cmd_list(message: Message):
    """Список доступных конспектов — для учеников."""
    if not is_admin(message.from_user.id):
        if not await db.is_student(message.from_user.id, message.from_user.username):
            await message.answer(NO_ACCESS)
            return

    notes = await db.list_notes()
    if not notes:
        await message.answer("📭 Конспектов пока нет.")
        return

    lines = ["📚 Доступные конспекты:\n"]
    for number, title in notes:
        lines.append(f"№{number} — {title}")
    await message.answer("\n".join(lines))


@router.message(F.text.regexp(r"^\s*\d+\s*$"))
async def handle_number(message: Message):
    """Пользователь прислал число — выдаём конспект."""
    user_id = message.from_user.id
    username = message.from_user.username

    if not is_admin(user_id) and not await db.is_student(user_id, username):
        await message.answer(NO_ACCESS)
        return

    try:
        number = int(message.text.strip())
    except ValueError:
        await message.answer("Введите номер конспекта числом, например: 29")
        return

    note = await db.get_note(number)
    if not note:
        await message.answer(f"❌ Конспект №{number} не найден.")
        return

    _, title, file_path, file_id = note
    caption = f"📘 Конспект №{number}\nТема: {title}"

    try:
        # Сначала пробуем по file_id — быстрее и не грузит диск.
        if file_id:
            await message.answer_document(file_id, caption=caption)
            return
    except Exception as e:
        logger.warning("Не удалось отправить по file_id (%s), пробую файл с диска", e)

    if not os.path.exists(file_path):
        logger.error("Файл не найден на диске: %s", file_path)
        await message.answer("⚠️ Файл конспекта не найден на сервере. Сообщите администратору.")
        return

    try:
        new_msg = await message.answer_document(FSInputFile(file_path), caption=caption)
        # Обновим file_id, чтобы в следующий раз отправить быстрее.
        if new_msg.document and new_msg.document.file_id:
            await db.upsert_note(number, title, file_path, new_msg.document.file_id)
    except Exception as e:
        logger.exception("Ошибка отправки PDF: %s", e)
        await message.answer("⚠️ Не удалось отправить файл. Попробуйте позже.")


@router.message(F.text)
async def fallback_text(message: Message):
    """Любой другой текст — мягкая подсказка."""
    if is_admin(message.from_user.id):
        return  # админу подсказку не шлём, у него свои сценарии

    if not await db.is_student(message.from_user.id, message.from_user.username):
        await message.answer(NO_ACCESS)
        return

    await message.answer(
        "Введите номер конспекта числом, например: 29\n"
        "Или команду /list — увидите список доступных конспектов."
    )
