import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import FILES_DIR
from database import (
    add_student,
    remove_student,
    get_students,
    get_notes,
    note_exists,
    save_note,
    delete_note
)
from keyboards import replace_note_keyboard
from utils import is_admin, is_valid_number, normalize_student_value, logger

router = Router()


class UploadNote(StatesGroup):
    waiting_number = State()
    waiting_title = State()
    waiting_replace_confirm = State()


def admin_only(message: Message):
    return is_admin(message.from_user.id)


async def save_uploaded_pdf(bot: Bot, document, number: int, title: str):
    file_path = os.path.join(FILES_DIR, f"note_{number}.pdf")

    await bot.download(
        document,
        destination=file_path
    )

    save_note(
        number=number,
        title=title,
        file_path=file_path,
        file_id=document.file_id
    )


@router.message(Command("add_student"))
async def add_student_handler(message: Message):
    if not admin_only(message):
        return

    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("Использование: /add_student 123456789 или /add_student @username")
        return

    try:
        value = normalize_student_value(args[1])
        add_student(value)
        await message.answer(f"✅ Ученик добавлен: {value}")
    except Exception as e:
        logger.exception(e)
        await message.answer("Ошибка. Введите ID или @username.")


@router.message(Command("add_students"))
async def add_students_handler(message: Message):
    if not admin_only(message):
        return

    values = message.text.split()[1:]

    if not values:
        await message.answer("Использование: /add_students @user1 @user2 123456789")
        return

    added = []
    errors = []

    for value in values:
        try:
            normalized = normalize_student_value(value)
            add_student(normalized)
            added.append(normalized)
        except Exception:
            errors.append(value)

    text = ""

    if added:
        text += "✅ Добавлены:\n" + "\n".join(added)

    if errors:
        text += "\n\n⚠️ Ошибка в данных:\n" + "\n".join(errors)

    await message.answer(text)


@router.message(Command("remove_student"))
async def remove_student_handler(message: Message):
    if not admin_only(message):
        return

    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("Использование: /remove_student 123456789 или /remove_student @username")
        return

    try:
        value = normalize_student_value(args[1])
        deleted = remove_student(value)

        if deleted:
            await message.answer(f"✅ Ученик удалён: {value}")
        else:
            await message.answer("Ученик не найден.")
    except Exception as e:
        logger.exception(e)
        await message.answer("Ошибка. Введите ID или @username.")


@router.message(Command("students"))
async def students_handler(message: Message):
    if not admin_only(message):
        return

    students = get_students()

    if not students:
        await message.answer("Список учеников пуст.")
        return

    text = "👥 Ученики:\n\n"

    for telegram_id, username, added_at in students:
        if telegram_id:
            text += f"ID: {telegram_id} | добавлен: {added_at}\n"
        else:
            text += f"@{username} | добавлен: {added_at}\n"

    await message.answer(text)


@router.message(Command("notes"))
async def notes_handler(message: Message):
    if not admin_only(message):
        return

    notes = get_notes()

    if not notes:
        await message.answer("Конспектов пока нет.")
        return

    text = "📚 Конспекты:\n\n"

    for number, title, created_at, updated_at in notes:
        text += f"№{number} — {title}\n"

    await message.answer(text)


@router.message(Command("delete_note"))
async def delete_note_handler(message: Message):
    if not admin_only(message):
        return

    args = message.text.split(maxsplit=1)

    if len(args) < 2 or not is_valid_number(args[1]):
        await message.answer("Использование: /delete_note 29")
        return

    number = int(args[1])
    note = delete_note(number)

    if not note:
        await message.answer(f"Конспект №{number} не найден.")
        return

    _, title, file_path, _ = note

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logger.exception(e)

    await message.answer(f"✅ Конспект №{number} удалён.\nТема: {title}")


@router.message(F.document)
async def upload_pdf_handler(message: Message, state: FSMContext):
    if not admin_only(message):
        return

    document = message.document

    if document.mime_type != "application/pdf" and not document.file_name.lower().endswith(".pdf"):
        await message.answer("Отправьте именно PDF-файл.")
        return

    await state.clear()
    await state.update_data(document=document.model_dump())

    await state.set_state(UploadNote.waiting_number)
    await message.answer("Введите номер конспекта:")


@router.message(UploadNote.waiting_number)
async def note_number_handler(message: Message, state: FSMContext):
    if not admin_only(message):
        return

    if not is_valid_number(message.text.strip()):
        await message.answer("Введите корректный номер. Например: 29")
        return

    number = int(message.text.strip())

    await state.update_data(number=number)
    await state.set_state(UploadNote.waiting_title)
    await message.answer("Введите тему конспекта:")


@router.message(UploadNote.waiting_title)
async def note_title_handler(message: Message, state: FSMContext, bot: Bot):
    if not admin_only(message):
        return

    title = message.text.strip()

    if len(title) < 2:
        await message.answer("Введите нормальную тему конспекта.")
        return

    data = await state.get_data()
    number = data["number"]
    document_data = data["document"]

    from aiogram.types import Document
    document = Document(**document_data)

    await state.update_data(title=title)

    if note_exists(number):
        await state.set_state(UploadNote.waiting_replace_confirm)
        await message.answer(
            f"Конспект №{number} уже существует. Заменить?",
            reply_markup=replace_note_keyboard(number)
        )
        return

    try:
        await save_uploaded_pdf(bot, document, number, title)
        await state.clear()

        await message.answer(
            f"✅ Конспект сохранён!\n\n"
            f"📘 Конспект №{number}\n"
            f"Тема: {title}"
        )
    except Exception as e:
        logger.exception(e)
        await state.clear()
        await message.answer("Ошибка при сохранении PDF.")


@router.callback_query(F.data.startswith("replace_note:"))
async def replace_note_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()

    if not data:
        await callback.message.answer("Данные загрузки потеряны. Отправьте PDF заново.")
        await callback.answer()
        return

    from aiogram.types import Document

    number = data["number"]
    title = data["title"]
    document = Document(**data["document"])

    try:
        await save_uploaded_pdf(bot, document, number, title)
        await state.clear()

        await callback.message.edit_text(
            f"✅ Конспект заменён!\n\n"
            f"📘 Конспект №{number}\n"
            f"Тема: {title}"
        )
    except Exception as e:
        logger.exception(e)
        await callback.message.answer("Ошибка при замене PDF.")

    await callback.answer()


@router.callback_query(F.data == "cancel_replace")
async def cancel_replace_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text("❌ Замена отменена.")
    await callback.answer()
