import logging
import os
from typing import Any, Awaitable, Callable

from aiogram import Router, F, Bot, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, TelegramObject

import database as db
from config import FILES_DIR
from keyboards import replace_confirm_kb
from utils import is_admin, parse_identifier

logger = logging.getLogger(__name__)
router = Router(name="admin")


class AdminOnlyMiddleware(BaseMiddleware):
    """Пропускает дальше только админа. Остальные события пойдут в следующий роутер."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or not is_admin(user.id):
            return  # пропускаем — диспетчер передаст событие следующему роутеру
        return await handler(event, data)


router.message.middleware(AdminOnlyMiddleware())
router.callback_query.middleware(AdminOnlyMiddleware())


class UploadStates(StatesGroup):
    waiting_number = State()
    waiting_title = State()
    waiting_replace_confirm = State()


# ---------- управление учениками ----------

@router.message(Command("add_student"))
async def cmd_add_student(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Используйте: /add_student <telegram_id или @username>\n"
            "Пример: /add_student 123456789\n"
            "Пример: /add_student @ivan"
        )
        return

    tg_id, username = parse_identifier(parts[1])
    if tg_id is None and not username:
        await message.answer("⚠️ Не понял идентификатор. Используйте число или @username.")
        return

    status = await db.add_student(telegram_id=tg_id, username=username)
    label = f"@{username}" if username else str(tg_id)
    if status == "added":
        await message.answer(f"✅ Ученик {label} добавлен.")
    elif status == "exists":
        await message.answer(f"ℹ️ Ученик {label} уже есть в списке.")
    else:
        await message.answer("⚠️ Не удалось добавить.")


@router.message(Command("add_students"))
async def cmd_add_students(message: Message):
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            "Используйте: /add_students <id или @username> [еще ...]\n"
            "Пример: /add_students @user1 @user2 123456789"
        )
        return

    added, exists, invalid = [], [], []
    for token in parts[1:]:
        tg_id, username = parse_identifier(token)
        if tg_id is None and not username:
            invalid.append(token)
            continue
        status = await db.add_student(telegram_id=tg_id, username=username)
        label = f"@{username}" if username else str(tg_id)
        if status == "added":
            added.append(label)
        elif status == "exists":
            exists.append(label)
        else:
            invalid.append(token)

    lines = []
    if added:
        lines.append("✅ Добавлены: " + ", ".join(added))
    if exists:
        lines.append("ℹ️ Уже были: " + ", ".join(exists))
    if invalid:
        lines.append("⚠️ Не распознаны: " + ", ".join(invalid))
    await message.answer("\n".join(lines) if lines else "Ничего не изменилось.")


@router.message(Command("remove_student"))
async def cmd_remove_student(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Используйте: /remove_student <telegram_id или @username>")
        return

    tg_id, username = parse_identifier(parts[1])
    if tg_id is None and not username:
        await message.answer("⚠️ Не понял идентификатор.")
        return

    ok = await db.remove_student(telegram_id=tg_id, username=username)
    label = f"@{username}" if username else str(tg_id)
    if ok:
        await message.answer(f"🗑 Ученик {label} удалён.")
    else:
        await message.answer(f"❌ Ученик {label} не найден.")


@router.message(Command("students"))
async def cmd_students(message: Message):
    rows = await db.list_students()
    if not rows:
        await message.answer("👥 Список учеников пуст.")
        return
    lines = ["👥 Ученики:\n"]
    for tg_id, username, added_at in rows:
        ident = f"@{username}" if username else str(tg_id)
        lines.append(f"• {ident}  (добавлен: {added_at[:10]})")
    await message.answer("\n".join(lines))


# ---------- управление конспектами ----------

@router.message(Command("notes"))
async def cmd_notes(message: Message):
    notes = await db.list_notes()
    if not notes:
        await message.answer("📭 Конспектов пока нет.")
        return
    lines = ["📚 Все конспекты:\n"]
    for number, title in notes:
        lines.append(f"№{number} — {title}")
    await message.answer("\n".join(lines))


@router.message(Command("delete_note"))
async def cmd_delete_note(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Используйте: /delete_note <номер>")
        return

    number = int(parts[1].strip())
    file_path = await db.delete_note(number)
    if file_path is None:
        await message.answer(f"❌ Конспект №{number} не найден.")
        return

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            logger.warning("Не удалось удалить файл %s: %s", file_path, e)

    await message.answer(f"🗑 Конспект №{number} удалён.")


# ---------- загрузка PDF (FSM) ----------

@router.message(F.document)
async def on_document(message: Message, state: FSMContext):
    doc = message.document
    if not doc:
        return

    mime = (doc.mime_type or "").lower()
    name = (doc.file_name or "").lower()
    if mime != "application/pdf" and not name.endswith(".pdf"):
        await message.answer("⚠️ Принимаются только PDF-файлы.")
        return

    await state.update_data(file_id=doc.file_id, original_name=doc.file_name)
    await state.set_state(UploadStates.waiting_number)
    await message.answer("Введите номер конспекта:")


@router.message(UploadStates.waiting_number, F.text)
async def upload_get_number(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Номер должен быть числом. Введите ещё раз:")
        return

    number = int(text)
    existing = await db.get_note(number)
    if existing:
        await state.update_data(number=number)
        await state.set_state(UploadStates.waiting_replace_confirm)
        await message.answer(
            f"Конспект №{number} уже существует. Заменить?",
            reply_markup=replace_confirm_kb(number),
        )
        return

    await state.update_data(number=number)
    await state.set_state(UploadStates.waiting_title)
    await message.answer("Введите тему конспекта:")


@router.callback_query(UploadStates.waiting_replace_confirm, F.data.startswith("replace:"))
async def upload_replace_confirm(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else "no"

    if action == "yes":
        await state.set_state(UploadStates.waiting_title)
        await call.message.edit_text("✅ Окей, заменяем. Введите тему конспекта:")
    else:
        await state.clear()
        await call.message.edit_text("❌ Отменено.")
    await call.answer()


@router.message(UploadStates.waiting_title, F.text)
async def upload_get_title(message: Message, state: FSMContext, bot: Bot):
    title = (message.text or "").strip()
    if not title:
        await message.answer("Тема не может быть пустой. Введите тему конспекта:")
        return

    data = await state.get_data()
    file_id = data.get("file_id")
    number = data.get("number")

    if not file_id or number is None:
        await state.clear()
        await message.answer("⚠️ Что-то пошло не так. Загрузите PDF заново.")
        return

    target_path = FILES_DIR / f"note_{number}.pdf"

    try:
        tg_file = await bot.get_file(file_id)
        await bot.download_file(tg_file.file_path, destination=str(target_path))
    except Exception as e:
        logger.exception("Ошибка скачивания файла: %s", e)
        await state.clear()
        await message.answer("⚠️ Не удалось скачать файл. Попробуйте ещё раз.")
        return

    status = await db.upsert_note(
        number=number,
        title=title,
        file_path=str(target_path),
        file_id=file_id,
    )
    await state.clear()

    if status == "added":
        await message.answer(f"✅ Конспект №{number} «{title}» сохранён.")
    else:
        await message.answer(f"♻️ Конспект №{number} обновлён, новая тема: «{title}».")


@router.message(UploadStates.waiting_number)
async def upload_number_wrong_type(message: Message):
    await message.answer("Ожидаю номер конспекта числом. Например: 29")


@router.message(UploadStates.waiting_title)
async def upload_title_wrong_type(message: Message):
    await message.answer("Ожидаю тему конспекта текстом.")
