import logging
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile

from config import ADMIN_ID
from database import is_student, get_note, list_notes
from utils import is_admin

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def start(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(
            "Здравствуйте, администратор 👑\n"
            "Вы можете:\n"
            "📌 загрузить PDF-конспект (просто отправьте PDF)\n"
            "📌 добавить ученика — /add_student <id|@username>\n"
            "📌 массово — /add_students @u1 @u2 ...\n"
            "📌 удалить ученика — /remove_student <id|@username>\n"
            "📌 список учеников — /students\n"
            "📌 список конспектов — /notes\n"
            "📌 удалить конспект — /delete_note <номер>"
        )
        return

    await message.answer(
        "Здравствуйте! 👋\n"
        "Введите номер конспекта, например: 29\n"
        "И я отправлю вам нужный PDF-файл."
    )


@router.message(Command("list"))
async def cmd_list(message: Message):
    # ученики тоже могут смотреть, но только если у них есть доступ
    if not is_admin(message.from_user.id):
        allowed = await is_student(message.from_user.id, message.from_user.username)
        if not allowed:
            await message.answer("⛔ У вас нет доступа к конспектам. Обратитесь к администратору.")
            return

    notes = await list_notes()
    if not notes:
        await message.answer("Пока нет ни одного конспекта.")
        return

    text = "📚 Доступные конспекты:\n\n"
    text += "\n".join(f"№{n['number']} — {n['title']}" for n in notes)
    await message.answer(text)


@router.message(F.text.regexp(r"^\s*\d+\s*$"))
async def send_note(message: Message):
    # админу тоже отвечаем, чтобы он мог проверить
    if not is_admin(message.from_user.id):
        allowed = await is_student(message.from_user.id, message.from_user.username)
        if not allowed:
            await message.answer("⛔ У вас нет доступа к конспектам. Обратитесь к администратору.")
            return

    try:
        number = int(message.text.strip())
    except ValueError:
        return

    note = await get_note(number)
    if not note:
        await message.answer(f"Конспект №{number} не найден. Посмотрите список: /list")
        return

    # сначала пробуем по file_id (быстрее), потом по файлу
    try:
        if note.get("file_id"):
            await message.answer_document(
                document=note["file_id"],
                caption=f"📘 Конспект №{note['number']}\nТема: {note['title']}",
            )
            return
    except Exception as e:
        logger.warning("file_id не сработал для конспекта %s: %s", number, e)

    file_path = Path(note["file_path"])
    if not file_path.exists():
        logger.error("PDF не найден на диске: %s", file_path)
        await message.answer("⚠️ Файл конспекта не найден на сервере. Сообщите администратору.")
        return

    try:
        await message.answer_document(
            document=FSInputFile(file_path),
            caption=f"📘 Конспект №{note['number']}\nТема: {note['title']}",
        )
    except Exception as e:
        logger.exception("Ошибка отправки конспекта %s: %s", number, e)
        await message.answer("⚠️ Не удалось отправить файл. Попробуйте позже.")


@router.message(F.text)
async def fallback(message: Message):
    if is_admin(message.from_user.id):
        return  # админу не мешаем — у него свои хендлеры
    await message.answer("Введите номер конспекта цифрами, например: 29\nИли /list — список доступных.")
