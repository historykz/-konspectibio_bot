import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config import FILES_DIR
from database import (
    add_student,
    remove_student,
    list_students,
    save_note,
    delete_note,
    get_note,
    list_notes,
)
from keyboards import replace_confirm_kb
from utils import is_admin, parse_identifier

router = Router()
logger = logging.getLogger(__name__)


class UploadStates(StatesGroup):
    waiting_number = State()
    waiting_title = State()
    waiting_replace_confirm = State()


# фильтр: только админ
@router.message(Command("add_student"))
async def add_student_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /add_student <telegram_id или @username>")
        return
    tg_id, uname = parse_identifier(parts[1])
    if not tg_id and not uname:
        await message.answer("Не понял идентификатор.")
        return
    added = await add_student(telegram_id=tg_id, username=uname)
    if added:
        await message.answer(f"✅ Ученик добавлен: {parts[1]}")
    else:
        await message.answer(f"ℹ️ Ученик уже был в списке: {parts[1]}")


@router.message(Command("add_students"))
async def add_students_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()[1:]
    if not parts:
        await message.answer("Использование: /add_students @user1 @user2 123456789 ...")
        return
    added, skipped = [], []
    for p in parts:
        tg_id, uname = parse_identifier(p)
        if not tg_id and not uname:
            skipped.append(p)
            continue
        ok = await add_student(telegram_id=tg_id, username=uname)
        (added if ok else skipped).append(p)
    text = ""
    if added:
        text += f"✅ Добавлены ({len(added)}): " + ", ".join(added) + "\n"
    if skipped:
        text += f"ℹ️ Пропущены ({len(skipped)}): " + ", ".join(skipped)
    await message.answer(text or "Ничего не добавлено.")


@router.message(Command("remove_student"))
async def remove_student_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /remove_student <telegram_id или @username>")
        return
    tg_id, uname = parse_identifier(parts[1])
    removed = await remove_student(telegram_id=tg_id, username=uname)
    if removed:
        await message.answer(f"✅ Ученик удалён: {parts[1]}")
    else:
        await message.answer(f"ℹ️ Ученик не найден: {parts[1]}")


@router.message(Command("students"))
async def students_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    students = await list_students()
    if not students:
        await message.answer("Список учеников пуст.")
        return
    lines = ["👥 Ученики:\n"]
    for s in students:
        ident = []
        if s["username"]:
            ident.append("@" + s["username"])
        if s["telegram_id"]:
            ident.append(str(s["telegram_id"]))
        lines.append(" | ".join(ident) if ident else "—")
    await message.answer("\n".join(lines))


@router.message(Command("notes"))
async def notes_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    notes = await list_notes()
    if not notes:
        await message.answer("Конспектов пока нет.")
        return
    text = "📚 Конспекты:\n\n" + "\n".join(f"№{n['number']} — {n['title']}" for n in notes)
    await message.answer(text)


@router.message(Command("delete_note"))
async def delete_note_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Использование: /delete_note <номер>")
        return
    number = int(parts[1].strip())
    note = await delete_note(number)
    if not note:
        await message.answer(f"Конспект №{number} не найден.")
        return
    # удаляем сам файл
    try:
        Path(note["file_path"]).unlink(missing_ok=True)
    except Exception as e:
        logger.warning("Не удалось удалить файл %s: %s", note["file_path"], e)
    await message.answer(f"🗑 Конспект №{number} удалён.")


# ---------- ЗАГРУЗКА PDF ----------

@router.message(F.document)
async def receive_pdf(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    doc = message.document
    mime = (doc.mime_type or "").lower()
    name = (doc.file_name or "").lower()
    if mime != "application/pdf" and not name.endswith(".pdf"):
        await message.answer("Это не PDF. Пришлите файл в формате PDF.")
        return

    await state.update_data(file_id=doc.file_id, original_name=doc.file_name)
    await state.set_state(UploadStates.waiting_number)
    await message.answer("Введите номер конспекта:")


@router.message(UploadStates.waiting_number, F.text)
async def receive_number(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("Номер должен быть числом. Попробуйте ещё раз:")
        return
    number = int(text)
    existing = await get_note(number)
    await state.update_data(number=number)

    if existing:
        await state.set_state(UploadStates.waiting_replace_confirm)
        await message.answer(
            f"Конспект №{number} уже существует (тема: {existing['title']}).\nЗаменить?",
            reply_markup=replace_confirm_kb(number),
        )
        return

    await state.set_state(UploadStates.waiting_title)
    await message.answer("Введите тему конспекта:")


@router.callback_query(UploadStates.waiting_replace_confirm, F.data.startswith("replace:"))
async def replace_callback(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer()
        return
    _, decision, *_ = cb.data.split(":")
    if decision == "no":
        await state.clear()
        await cb.message.edit_text("❌ Замена отменена.")
        await cb.answer()
        return
    # yes
    await state.set_state(UploadStates.waiting_title)
    await cb.message.edit_text("Окей, заменяем. Введите новую тему конспекта:")
    await cb.answer()


@router.message(UploadStates.waiting_title, F.text)
async def receive_title(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    title = message.text.strip()
    if not title:
        await message.answer("Тема не может быть пустой. Введите ещё раз:")
        return

    data = await state.get_data()
    file_id = data["file_id"]
    number = data["number"]

    # скачиваем файл и сохраняем под номером
    file_path = FILES_DIR / f"{number}.pdf"
    try:
        # если был старый файл — удаляем (на случай замены)
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        tg_file = await bot.get_file(file_id)
        await bot.download_file(tg_file.file_path, destination=file_path)
    except Exception as e:
        logger.exception("Ошибка скачивания PDF: %s", e)
        await message.answer("⚠️ Не удалось сохранить файл. Попробуйте ещё раз.")
        await state.clear()
        return

    await save_note(number=number, title=title, file_path=str(file_path), file_id=file_id)
    await state.clear()
    await message.answer(f"✅ Конспект №{number} сохранён.\nТема: {title}")
