import os
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from config import ADMIN_ID
from database import is_student_allowed, get_note, get_notes
from utils import is_valid_number, is_admin, logger

router = Router()


@router.message(F.text == "/start")
async def start_handler(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(
            "Здравствуйте, администратор 👑\n\n"
            "Вы можете:\n"
            "📌 загрузить PDF-конспект\n"
            "📌 добавить ученика\n"
            "📌 удалить ученика\n"
            "📌 заменить конспект\n"
            "📌 посмотреть список конспектов\n\n"
            "Команды:\n"
            "/add_student 123456789\n"
            "/add_students @user1 @user2\n"
            "/remove_student 123456789\n"
            "/students\n"
            "/notes\n"
            "/delete_note 29"
        )
        return

    await message.answer(
        "Здравствуйте! 👋\n"
        "Введите номер конспекта, например: 29\n"
        "И я отправлю вам нужный PDF-файл."
    )


@router.message(F.text == "/list")
async def list_notes_handler(message: Message):
    if not is_admin(message.from_user.id):
        allowed = is_student_allowed(
            telegram_id=message.from_user.id,
            username=message.from_user.username
        )

        if not allowed:
            await message.answer(
                "⛔ У вас нет доступа к конспектам. Обратитесь к администратору."
            )
            return

    notes = get_notes()

    if not notes:
        await message.answer("Пока нет загруженных конспектов.")
        return

    text = "📚 Список доступных конспектов:\n\n"

    for number, title, created_at, updated_at in notes:
        text += f"№{number} — {title}\n"

    await message.answer(text)


@router.message(F.text)
async def get_note_by_number_handler(message: Message):
    text = message.text.strip()

    if text.startswith("/"):
        return

    if not is_valid_number(text):
        await message.answer("Введите только номер конспекта. Например: 29")
        return

    if not is_admin(message.from_user.id):
        allowed = is_student_allowed(
            telegram_id=message.from_user.id,
            username=message.from_user.username
        )

        if not allowed:
            await message.answer(
                "⛔ У вас нет доступа к конспектам. Обратитесь к администратору."
            )
            return

    number = int(text)
    note = get_note(number)

    if not note:
        await message.answer(f"Конспект №{number} не найден.")
        return

    note_number, title, file_path, file_id = note

    try:
        caption = f"📘 Конспект №{note_number}\nТема: {title}"

        if os.path.exists(file_path):
            await message.answer_document(
                document=FSInputFile(file_path),
                caption=caption
            )
        elif file_id:
            await message.answer_document(
                document=file_id,
                caption=caption
            )
        else:
            await message.answer("PDF-файл не найден. Обратитесь к администратору.")

    except Exception as e:
        logger.exception(e)
        await message.answer("Произошла ошибка при отправке PDF.")
