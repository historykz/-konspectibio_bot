import logging
import os
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

import database as db
from keyboards import cancel_kb, submit_photo_kb, main_menu_kb
from states import SubmitWorkbook
from services.file_service import save_temp_photo, clear_temp_dir, delete_file
from services.pdf_service import photos_to_pdf
from services.access_service import get_role, has_access

logger = logging.getLogger(__name__)
router = Router()


# ── CHECKLIST FILE DELIVERY ─────────────────────────────────────────────────

@router.message(F.text.regexp(r"^\d+$"))
async def handle_checklist_number(message: Message, state: FSMContext):
    """Fallback handler for checklist numbers - only if no workbook was found."""
    current = await state.get_state()
    if current is not None:
        return

    if not await has_access(message.from_user.id):
        return

    serial = int(message.text.strip())
    cl = await db.get_checklist_by_serial(serial)
    if cl and os.path.exists(cl["file_path"]):
        file = FSInputFile(cl["file_path"])
        await message.answer_document(
            file,
            caption=f"✅ <b>Чек-лист №{cl['serial_number']}</b>\nТема: {cl['title']}\n\nФайл прикреплён ниже.",
            parse_mode="HTML"
        )


# ── SUBMIT WORKBOOK ─────────────────────────────────────────────────────────

@router.message(F.text == "📤 Сдать РТ")
async def submit_start(message: Message, state: FSMContext):
    await state.clear()
    tg_id = message.from_user.id
    student = await db.get_student_by_telegram_id(tg_id)
    if not student:
        await message.answer(
            "⛔ Вы пока не прикреплены к куратору.\n"
            "Обратитесь к администратору."
        )
        return

    if not student.get("curator_id"):
        await message.answer("⛔ У вас не назначен куратор.")
        return

    await state.set_state(SubmitWorkbook.waiting_full_name)
    await message.answer(
        "📝 Введите ваше ФИО полностью:\n\nПример: <i>Иванов Иван Иванович</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@router.message(SubmitWorkbook.waiting_full_name)
async def submit_get_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("❌ Введите полное ФИО.")
        return
    await state.update_data(full_name=full_name, photo_count=0)
    await state.set_state(SubmitWorkbook.collecting_photos)
    await message.answer(
        f"✅ ФИО сохранено: <b>{full_name}</b>\n\n"
        f"📸 Теперь отправьте фотографии выполненной рабочей тетради:",
        parse_mode="HTML"
    )


@router.message(SubmitWorkbook.collecting_photos, F.photo)
async def submit_photo(message: Message, state: FSMContext, bot: Bot):
    tg_id = message.from_user.id
    data = await state.get_data()
    photo_count = data.get("photo_count", 0)

    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file_info.file_path)

    path = save_temp_photo(file_bytes.read(), tg_id, photo_count)
    await db.add_photo_to_buffer(tg_id, path, photo_count)
    photo_count += 1
    await state.update_data(photo_count=photo_count)

    await message.answer(
        f"✅ Фото #{photo_count} добавлено.\n"
        f"Отправьте следующее фото или нажмите кнопку ниже:",
        reply_markup=submit_photo_kb()
    )


@router.message(SubmitWorkbook.collecting_photos)
async def submit_not_photo(message: Message):
    await message.answer(
        "📸 Пожалуйста, отправьте фотографии или нажмите кнопку ниже:",
        reply_markup=submit_photo_kb()
    )


@router.callback_query(F.data == "submit_cancel")
async def submit_cancel(callback: CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    await state.clear()
    await db.clear_buffer(tg_id)
    clear_temp_dir(tg_id)
    role = await get_role(tg_id)
    await callback.message.answer("❌ Сдача РТ отменена.", reply_markup=main_menu_kb(role))
    await callback.answer()


@router.callback_query(F.data == "submit_pdf")
async def submit_pdf(callback: CallbackQuery, state: FSMContext, bot: Bot):
    tg_id = callback.from_user.id
    data = await state.get_data()
    full_name = data.get("full_name", "Неизвестно")

    count = await db.count_buffer(tg_id)
    if count == 0:
        await callback.answer("❌ Сначала отправьте фотографии!", show_alert=True)
        return

    await callback.message.answer("⏳ Создаю PDF, подождите...")

    photos = await db.get_buffer_photos(tg_id)
    photo_paths = [p["photo_path"] for p in photos]

    pdf_path = await photos_to_pdf(photo_paths, tg_id)
    if not pdf_path:
        await callback.message.answer("❌ Ошибка при создании PDF. Попробуйте ещё раз.")
        await callback.answer()
        return

    student = await db.get_student_by_telegram_id(tg_id)
    if not student:
        await callback.message.answer("❌ Ошибка: ученик не найден.")
        await callback.answer()
        return

    curator = await db.get_curator_by_id(student["curator_id"])
    if not curator:
        await callback.message.answer("❌ Ошибка: куратор не найден.")
        await callback.answer()
        return

    group = await db.get_group_by_id(student["group_id"]) if student.get("group_id") else None

    submission = await db.create_submission(
        student["id"], curator["id"], student.get("group_id"),
        pdf_path, full_name
    )

    now = datetime.now()

    # Send to curator
    try:
        pdf_file = FSInputFile(pdf_path)
        await bot.send_document(
            curator["telegram_id"],
            pdf_file,
            caption=(
                f"📥 <b>Новая сданная РТ</b>\n\n"
                f"👨‍🎓 ФИО: <b>{full_name}</b>\n"
                f"Username: @{student.get('username') or '—'}\n"
                f"ID: <code>{tg_id}</code>\n"
                f"Группа: <b>{group['title'] if group else '—'}</b>\n"
                f"Дата: {now.strftime('%d.%m.%Y')}\n"
                f"Время: {now.strftime('%H:%M')}"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to send PDF to curator {curator['telegram_id']}: {e}")

    # Cleanup
    await db.clear_buffer(tg_id)
    clear_temp_dir(tg_id)
    await state.clear()

    role = await get_role(tg_id)
    await callback.message.answer(
        "✅ <b>Ваша рабочая тетрадь отправлена куратору.</b>",
        parse_mode="HTML",
        reply_markup=main_menu_kb(role)
    )
    await callback.answer()
