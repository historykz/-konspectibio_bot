import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, Document
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config import FILES_DIR
from database import (
    add_student, remove_student, get_students,
    get_notes, note_exists, save_note, delete_note
)
from keyboards import replace_note_keyboard
from utils import is_admin, is_positive_number, logger

router = Router()


class UploadNote(StatesGroup):
    waiting_number = State()
    waiting_title = State()
    waiting_confirm = State()


def admin_check(message: Message) -> bool:
    return is_admin(message.from_user.id)


async def save_uploaded_pdf(bot: Bot, document: Document, number: int, title: str):
    file_path = os.path.join(FILES_DIR, f"note_{number}.pdf")
    saved_path = None

    try:
        await bot.download(document, destination=file_path)
        saved_path = file_path
    except Exception as e:
        logger.exception("ÐÐµ ÑÐ´Ð°Ð»Ð¾ÑÑ ÑÐºÐ°ÑÐ°ÑÑ PDF Ð»Ð¾ÐºÐ°Ð»ÑÐ½Ð¾, ÑÐ¾ÑÑÐ°Ð½ÑÑ ÑÐ¾Ð»ÑÐºÐ¾ file_id: %s", e)

    save_note(number=number, title=title, file_path=saved_path, file_id=document.file_id)


@router.message(Command("add_student"))
async def cmd_add_student(message: Message):
    if not admin_check(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("ÐÑÐ¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°Ð½Ð¸Ðµ: /add_student 123456789 Ð¸Ð»Ð¸ /add_student @username")
        return
    try:
        added = add_student(parts[1])
        await message.answer(("â Ð£ÑÐµÐ½Ð¸Ðº Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½: " if added else "â¹ï¸ Ð£Ð¶Ðµ Ð±ÑÐ» Ð² ÑÐ¿Ð¸ÑÐºÐµ: ") + parts[1].strip())
    except Exception:
        await message.answer("ÐÑÐ¸Ð±ÐºÐ°. ÐÑÐ¶Ð½Ð¾ ÑÐºÐ°Ð·Ð°ÑÑ Telegram ID Ð¸Ð»Ð¸ @username.")


@router.message(Command("add_students"))
async def cmd_add_students(message: Message):
    if not admin_check(message):
        return
    values = message.text.split()[1:]
    if not values:
        await message.answer("ÐÑÐ¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°Ð½Ð¸Ðµ: /add_students @user1 @user2 123456789")
        return

    ok, bad = [], []
    for value in values:
        try:
            add_student(value)
            ok.append(value)
        except Exception:
            bad.append(value)

    text = ""
    if ok:
        text += "â ÐÐ¾Ð±Ð°Ð²Ð»ÐµÐ½Ñ:\n" + "\n".join(ok)
    if bad:
        text += "\n\nâ ï¸ ÐÐµ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ñ:\n" + "\n".join(bad)
    await message.answer(text)


@router.message(Command("remove_student"))
async def cmd_remove_student(message: Message):
    if not admin_check(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("ÐÑÐ¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°Ð½Ð¸Ðµ: /remove_student 123456789 Ð¸Ð»Ð¸ /remove_student @username")
        return
    try:
        removed = remove_student(parts[1])
        await message.answer("â Ð£ÑÐµÐ½Ð¸Ðº ÑÐ´Ð°Ð»ÑÐ½." if removed else "Ð£ÑÐµÐ½Ð¸Ðº Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½.")
    except Exception:
        await message.answer("ÐÑÐ¸Ð±ÐºÐ°. ÐÑÐ¶Ð½Ð¾ ÑÐºÐ°Ð·Ð°ÑÑ Telegram ID Ð¸Ð»Ð¸ @username.")


@router.message(Command("students"))
async def cmd_students(message: Message):
    if not admin_check(message):
        return
    students = get_students()
    if not students:
        await message.answer("Ð¡Ð¿Ð¸ÑÐ¾Ðº ÑÑÐµÐ½Ð¸ÐºÐ¾Ð² Ð¿ÑÑÑ.")
        return
    text = "ð¥ Ð£ÑÐµÐ½Ð¸ÐºÐ¸:\n\n"
    for row in students:
        text += f"{row['value']} | {row['added_at']}\n"
    await message.answer(text)


@router.message(Command("notes"))
async def cmd_notes(message: Message):
    if not admin_check(message):
        return
    notes = get_notes()
    if not notes:
        await message.answer("ÐÐ¾Ð½ÑÐ¿ÐµÐºÑÐ¾Ð² Ð¿Ð¾ÐºÐ° Ð½ÐµÑ.")
        return
    text = "ð ÐÐ¾Ð½ÑÐ¿ÐµÐºÑÑ:\n\n"
    for row in notes:
        text += f"â{row['number']} â {row['title']}\n"
    await message.answer(text)


@router.message(Command("delete_note"))
async def cmd_delete_note(message: Message):
    if not admin_check(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not is_positive_number(parts[1]):
        await message.answer("ÐÑÐ¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°Ð½Ð¸Ðµ: /delete_note 29")
        return
    number = int(parts[1])
    note = delete_note(number)
    if not note:
        await message.answer(f"ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ â{number} Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½.")
        return
    try:
        if note['file_path'] and os.path.exists(note['file_path']):
            os.remove(note['file_path'])
    except Exception as e:
        logger.exception(e)
    await message.answer(f"â ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ â{number} ÑÐ´Ð°Ð»ÑÐ½.")


@router.message(F.document)
async def upload_pdf(message: Message, state: FSMContext):
    if not admin_check(message):
        return
    document = message.document
    file_name = document.file_name or ""
    if document.mime_type != "application/pdf" and not file_name.lower().endswith(".pdf"):
        await message.answer("ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ PDF-ÑÐ°Ð¹Ð».")
        return
    await state.clear()
    await state.update_data(document=document.model_dump())
    await state.set_state(UploadNote.waiting_number)
    await message.answer("ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð½Ð¾Ð¼ÐµÑ ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ°:")


@router.message(UploadNote.waiting_number)
async def upload_number(message: Message, state: FSMContext):
    if not admin_check(message):
        return
    if not message.text or not is_positive_number(message.text):
        await message.answer("ÐÐ²ÐµÐ´Ð¸ÑÐµ ÐºÐ¾ÑÑÐµÐºÑÐ½ÑÐ¹ Ð½Ð¾Ð¼ÐµÑ. ÐÐ°Ð¿ÑÐ¸Ð¼ÐµÑ: 29")
        return
    await state.update_data(number=int(message.text.strip()))
    await state.set_state(UploadNote.waiting_title)
    await message.answer("ÐÐ²ÐµÐ´Ð¸ÑÐµ ÑÐµÐ¼Ñ ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ°:")


@router.message(UploadNote.waiting_title)
async def upload_title(message: Message, state: FSMContext, bot: Bot):
    if not admin_check(message):
        return
    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer("ÐÐ²ÐµÐ´Ð¸ÑÐµ ÑÐµÐ¼Ñ ÐºÐ¾Ð½ÑÐ¿ÐµÐºÑÐ°.")
        return
    data = await state.get_data()
    number = data["number"]
    await state.update_data(title=title)

    if note_exists(number):
        await state.set_state(UploadNote.waiting_confirm)
        await message.answer(f"ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ â{number} ÑÐ¶Ðµ ÑÑÑÐµÑÑÐ²ÑÐµÑ. ÐÐ°Ð¼ÐµÐ½Ð¸ÑÑ?", reply_markup=replace_note_keyboard(number))
        return

    document = Document(**data["document"])
    try:
        await save_uploaded_pdf(bot, document, number, title)
        await state.clear()
        await message.answer(f"â ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ ÑÐ¾ÑÑÐ°Ð½ÑÐ½!\n\nð ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ â{number}\nÐ¢ÐµÐ¼Ð°: {title}")
    except Exception as e:
        logger.exception(e)
        await state.clear()
        await message.answer("ÐÑÐ¸Ð±ÐºÐ° Ð¿ÑÐ¸ ÑÐ¾ÑÑÐ°Ð½ÐµÐ½Ð¸Ð¸ PDF.")


@router.callback_query(F.data.startswith("replace:"))
async def replace_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("ÐÐµÑ Ð´Ð¾ÑÑÑÐ¿Ð°", show_alert=True)
        return
    data = await state.get_data()
    if not data:
        await callback.message.answer("ÐÐ°Ð½Ð½ÑÐµ Ð¿Ð¾ÑÐµÑÑÐ½Ñ. ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ PDF Ð·Ð°Ð½Ð¾Ð²Ð¾.")
        await callback.answer()
        return
    document = Document(**data["document"])
    number = data["number"]
    title = data["title"]
    try:
        await save_uploaded_pdf(bot, document, number, title)
        await state.clear()
        await callback.message.edit_text(f"â ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ Ð·Ð°Ð¼ÐµÐ½ÑÐ½!\n\nð ÐÐ¾Ð½ÑÐ¿ÐµÐºÑ â{number}\nÐ¢ÐµÐ¼Ð°: {title}")
    except Exception as e:
        logger.exception(e)
        await callback.message.answer("ÐÑÐ¸Ð±ÐºÐ° Ð¿ÑÐ¸ Ð·Ð°Ð¼ÐµÐ½Ðµ PDF.")
    await callback.answer()


@router.callback_query(F.data == "cancel_replace")
async def cancel_replace(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("ÐÐµÑ Ð´Ð¾ÑÑÑÐ¿Ð°", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("â ÐÐ°Ð¼ÐµÐ½Ð° Ð¾ÑÐ¼ÐµÐ½ÐµÐ½Ð°.")
    await callback.answer()
