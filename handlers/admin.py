import logging
import os
import re
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import database as db
from config import ADMINS
from keyboards import (
    admin_panel_kb, cancel_kb, confirm_clear_kb, confirm_delete_kb,
    period_filter_kb, checklist_admin_kb, main_menu_kb
)
from states import (
    AdminAddWorkbook, AdminDeleteWorkbook, AdminAddCurator, AdminAddStudent,
    AdminGrantAccess, AdminRevokeAccess, AdminAddGroup, AdminAddChecklist, AdminDeleteChecklist
)
from services.file_service import save_workbook_file, save_checklist_file, delete_file, delete_files
from services.export_service import export_submissions_xlsx, export_bookings_xlsx
from services.access_service import get_role

logger = logging.getLogger(__name__)
router = Router()


def admin_only(func):
    import functools
    @functools.wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        if message.from_user.id not in ADMINS:
            await message.answer("â Ð£ Ð²Ð°Ñ Ð½ÐµÑ Ð´Ð¾ÑÑÑÐ¿Ð° Ðº ÑÑÐ¾Ð¼Ñ ÑÐ°Ð·Ð´ÐµÐ»Ñ.")
            return
        return await func(message, *args, **kwargs)
    return wrapper


# ââ ADD WORKBOOK âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

@router.message(F.text == "â ÐÐ¾Ð±Ð°Ð²Ð¸ÑÑ Ð Ð¢")
@admin_only
async def add_workbook_start(message: Message, state: FSMContext):
    await state.set_state(AdminAddWorkbook.waiting_file)
    await message.answer("ð ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ ÑÐ°Ð¹Ð» ÑÐ°Ð±Ð¾ÑÐµÐ¹ ÑÐµÑÑÐ°Ð´Ð¸ (PDF, DOCX, Ð¸ Ñ.Ð´.):", reply_markup=cancel_kb())


@router.message(AdminAddWorkbook.waiting_file, F.document)
async def add_workbook_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    file_info = await bot.get_file(doc.file_id)
    file_bytes = await bot.download_file(file_info.file_path)
    filename = f"wb_{doc.file_id}{os.path.splitext(doc.file_name or '.pdf')[1]}"
    path = save_workbook_file(file_bytes.read(), filename)
    await state.update_data(file_path=path, original_filename=doc.file_name)
    await state.set_state(AdminAddWorkbook.waiting_title)
    await message.answer("âï¸ ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ/ÑÐµÐ¼Ñ ÑÐ°Ð±Ð¾ÑÐµÐ¹ ÑÐµÑÑÐ°Ð´Ð¸:")


@router.message(AdminAddWorkbook.waiting_file)
async def add_workbook_file_wrong(message: Message):
    await message.answer("â ÐÐ¾Ð¶Ð°Ð»ÑÐ¹ÑÑÐ°, Ð¾ÑÐ¿ÑÐ°Ð²ÑÑÐµ ÑÐ°Ð¹Ð» Ð´Ð¾ÐºÑÐ¼ÐµÐ½ÑÐ°.")


@router.message(AdminAddWorkbook.waiting_title)
async def add_workbook_title(message: Message, state: FSMContext):
    title = message.text.strip()
    data = await state.get_data()
    wb = await db.add_workbook(title, data["file_path"], message.from_user.id)
    await state.clear()
    await message.answer(
        f"â <b>Ð Ð°Ð±Ð¾ÑÐ°Ñ ÑÐµÑÑÐ°Ð´Ñ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð°</b>\n\n"
        f"Ð¡ÐµÑÐ¸Ð¹Ð½ÑÐ¹ Ð½Ð¾Ð¼ÐµÑ: â{wb['serial_number']}\n"
        f"ÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ: {wb['title']}",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )


# ââ LIST WORKBOOKS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

@router.message(F.text == "ð Ð¡Ð¿Ð¸ÑÐ¾Ðº Ð Ð¢")
@admin_only
async def list_workbooks(message: Message, state: FSMContext):
    await state.clear()
    books = await db.get_all_workbooks()
    if not books:
        await message.answer("ð Ð Ð°Ð±Ð¾ÑÐ¸Ñ ÑÐµÑÑÐ°Ð´ÐµÐ¹ Ð¿Ð¾ÐºÐ° Ð½ÐµÑ.")
        return
    lines = ["ð <b>Ð¡Ð¿Ð¸ÑÐ¾Ðº ÑÐ°Ð±Ð¾ÑÐ¸Ñ ÑÐµÑÑÐ°Ð´ÐµÐ¹:</b>\n"]
    for b in books:
        lines.append(f"â{b['serial_number']} â {b['title']}")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ââ DELETE WORKBOOK ââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

@router.message(F.text == "ð Ð£Ð´Ð°Ð»Ð¸ÑÑ Ð Ð¢")
@admin_only
async def delete_workbook_start(message: Message, state: FSMContext):
    books = await db.get_all_workbooks()
    if not books:
        await message.answer("ð ÐÐµÑ ÑÐ°Ð±Ð¾ÑÐ¸Ñ ÑÐµÑÑÐ°Ð´ÐµÐ¹ Ð´Ð»Ñ ÑÐ´Ð°Ð»ÐµÐ½Ð¸Ñ.")
        return
    lines = ["ÐÐ²ÐµÐ´Ð¸ÑÐµ ÑÐµÑÐ¸Ð¹Ð½ÑÐ¹ Ð½Ð¾Ð¼ÐµÑ Ð Ð¢ Ð´Ð»Ñ ÑÐ´Ð°Ð»ÐµÐ½Ð¸Ñ:\n"]
    for b in books:
        lines.append(f"â{b['serial_number']} â {b['title']}")
    await state.set_state(AdminDeleteWorkbook.waiting_serial)
    await message.answer("\n".join(lines), reply_markup=cancel_kb())


@router.message(AdminDeleteWorkbook.waiting_serial)
async def delete_workbook_confirm(message: Message, state: FSMContext):
    try:
        serial = int(message.text.strip())
    except ValueError:
        await message.answer("â ÐÐ²ÐµÐ´Ð¸ÑÐµ ÑÐ¸ÑÐ»Ð¾.")
        return
    wb = await db.get_workbook_by_serial(serial)
    if not wb:
        await message.answer(f"â Ð Ð¢ â{serial} Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°.")
        return
    await state.update_data(serial=serial)
    await message.answer(
        f"â ï¸ Ð£Ð´Ð°Ð»Ð¸ÑÑ Ð Ð¢ â{serial} Â«{wb['title']}Â»?",
        reply_markup=confirm_delete_kb("wb", str(serial))
    )
    await state.clear()


@router.callback_query(F.data.startswith("confirm_delete_wb_"))
async def delete_workbook_do(callback: CallbackQuery):
    serial = int(callback.data.split("_")[-1])
    fp = await db.delete_workbook(serial)
    if fp:
        delete_file(fp)
    await callback.message.edit_text(f"â Ð Ð¢ â{serial} ÑÐ´Ð°Ð»ÐµÐ½Ð°.")
    await callback.answer()


# ââ CLEAR ALL WORKBOOKS ââââââââââââââââââââââââââââââââââââââââââââââââââââ

@router.message(F.text == "ð§¹ ÐÑÐ¸ÑÑÐ¸ÑÑ Ð²ÑÐµ Ð Ð¢")
@admin_only
async def clear_workbooks_ask(message: Message):
    await message.answer(
        "â ï¸ ÐÑ ÑÐ¾ÑÐ½Ð¾ ÑÐ¾ÑÐ¸ÑÐµ ÑÐ´Ð°Ð»Ð¸ÑÑ <b>Ð²ÑÐµ ÑÐ°Ð±Ð¾ÑÐ¸Ðµ ÑÐµÑÑÐ°Ð´Ð¸</b>?\nÐ­ÑÐ¾ Ð´ÐµÐ¹ÑÑÐ²Ð¸Ðµ Ð½ÐµÐ»ÑÐ·Ñ Ð¾ÑÐ¼ÐµÐ½Ð¸ÑÑ.",
        parse_mode="HTML",
        reply_markup=confirm_clear_kb("workbooks")
    )


@router.callback_query(F.data == "confirm_clear_workbooks")
async def clear_workbooks_do(callback: CallbackQuery):
    paths = await db.clear_all_workbooks()
    delete_files(paths)
    await callback.message.edit_text(f"â Ð£Ð´Ð°Ð»ÐµÐ½Ð¾ {len(paths)} ÑÐ°Ð±Ð¾ÑÐ¸Ñ ÑÐµÑÑÐ°Ð´ÐµÐ¹.")
    await callback.answer()


# ââ CHECKLIST MANAGEMENT âââââââââââââââââââââââââââââââââââââââââââââââââââ

@router.message(F.text == "â Ð£Ð¿ÑÐ°Ð²Ð»ÐµÐ½Ð¸Ðµ ÑÐµÐº-Ð»Ð¸ÑÑÐ°Ð¼Ð¸")
@admin_only
async def checklist_admin_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("â <b>Ð£Ð¿ÑÐ°Ð²Ð»ÐµÐ½Ð¸Ðµ ÑÐµÐº-Ð»Ð¸ÑÑÐ°Ð¼Ð¸</b>", parse_mode="HTML", reply_markup=checklist_admin_kb())


@router.message(F.text == "âï¸ ÐÐ°Ð·Ð°Ð´ Ð² Ð°Ð´Ð¼Ð¸Ð½-Ð¿Ð°Ð½ÐµÐ»Ñ")
@admin_only
async def back_to_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("âï¸ <b>ÐÐ´Ð¼Ð¸Ð½-Ð¿Ð°Ð½ÐµÐ»Ñ</b>", parse_mode="HTML", reply_markup=admin_panel_kb())


@router.message(F.text == "â ÐÐ¾Ð±Ð°Ð²Ð¸ÑÑ ÑÐµÐº-Ð»Ð¸ÑÑ")
@admin_only
async def add_checklist_start(message: Message, state: FSMContext):
    await state.set_state(AdminAddChecklist.waiting_file)
    await message.answer("ð ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ ÑÐ°Ð¹Ð» Ð¸Ð»Ð¸ ÑÐ¾ÑÐ¾ ÑÐµÐº-Ð»Ð¸ÑÑÐ°:", reply_markup=cancel_kb())


@router.message(AdminAddChecklist.waiting_file, F.document)
async def add_checklist_doc(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    file_info = await bot.get_file(doc.file_id)
    file_bytes = await bot.download_file(file_info.file_path)
    ext = os.path.splitext(doc.file_name or ".pdf")[1]
    filename = f"cl_{doc.file_id}{ext}"
    path = save_checklist_file(file_bytes.read(), filename)
    await state.update_data(file_path=path, file_type=ext.lstrip("."))
    await state.set_state(AdminAddChecklist.waiting_title)
    await message.answer("âï¸ ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ ÑÐµÐº-Ð»Ð¸ÑÑÐ°:")


@router.message(AdminAddChecklist.waiting_file, F.photo)
async def add_checklist_photo(message: Message, state: FSMContext, bot: Bot):
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file_info.file_path)
    filename = f"cl_{photo.file_id}.jpg"
    path = save_checklist_file(file_bytes.read(), filename)
    await state.update_data(file_path=path, file_type="jpg")
    await state.set_state(AdminAddChecklist.waiting_title)
    await message.answer("âï¸ ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ ÑÐµÐº-Ð»Ð¸ÑÑÐ°:")


@router.message(AdminAddChecklist.waiting_file)
async def add_checklist_wrong(message: Message):
    await message.answer("â ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ ÑÐ°Ð¹Ð» Ð¸Ð»Ð¸ ÑÐ¾ÑÐ¾.")


@router.message(AdminAddChecklist.waiting_title)
async def add_checklist_title(message: Message, state: FSMContext):
    title = message.text.strip()
    data = await state.get_data()
    cl = await db.add_checklist(title, data["file_path"], data.get("file_type", ""), message.from_user.id)
    await state.clear()
    await message.answer(
        f"â <b>Ð§ÐµÐº-Ð»Ð¸ÑÑ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½</b>\n\nÐ¡ÐµÑÐ¸Ð¹Ð½ÑÐ¹ Ð½Ð¾Ð¼ÐµÑ: â{cl['serial_number']}\nÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ: {cl['title']}",
        parse_mode="HTML",
        reply_markup=checklist_admin_kb()
    )


@router.message(F.text == "ð Ð¡Ð¿Ð¸ÑÐ¾Ðº ÑÐµÐº-Ð»Ð¸ÑÑÐ¾Ð²")
@admin_only
async def list_checklists(message: Message, state: FSMContext):
    await state.clear()
    items = await db.get_all_checklists()
    if not items:
        await message.answer("â Ð§ÐµÐº-Ð»Ð¸ÑÑÐ¾Ð² Ð¿Ð¾ÐºÐ° Ð½ÐµÑ.")
        return
    lines = ["â <b>Ð¡Ð¿Ð¸ÑÐ¾Ðº ÑÐµÐº-Ð»Ð¸ÑÑÐ¾Ð²:</b>\n"]
    for c in items:
        lines.append(f"â{c['serial_number']} â {c['title']}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "ð Ð£Ð´Ð°Ð»Ð¸ÑÑ ÑÐµÐº-Ð»Ð¸ÑÑ")
@admin_only
async def delete_checklist_start(message: Message, state: FSMContext):
    items = await db.get_all_checklists()
    if not items:
        await message.answer("â ÐÐµÑ ÑÐµÐº-Ð»Ð¸ÑÑÐ¾Ð² Ð´Ð»Ñ ÑÐ´Ð°Ð»ÐµÐ½Ð¸Ñ.")
        return
    lines = ["ÐÐ²ÐµÐ´Ð¸ÑÐµ ÑÐµÑÐ¸Ð¹Ð½ÑÐ¹ Ð½Ð¾Ð¼ÐµÑ ÑÐµÐº-Ð»Ð¸ÑÑÐ° Ð´Ð»Ñ ÑÐ´Ð°Ð»ÐµÐ½Ð¸Ñ:\n"]
    for c in items:
        lines.append(f"â{c['serial_number']} â {c['title']}")
    await state.set_state(AdminDeleteChecklist.waiting_serial)
    await message.answer("\n".join(lines), reply_markup=cancel_kb())


@router.message(AdminDeleteChecklist.waiting_serial)
async def delete_checklist_confirm(message: Message, state: FSMContext):
    try:
        serial = int(message.text.strip())
    except ValueError:
        await message.answer("â ÐÐ²ÐµÐ´Ð¸ÑÐµ ÑÐ¸ÑÐ»Ð¾.")
        return
    cl = await db.get_checklist_by_serial(serial)
    if not cl:
        await message.answer(f"â Ð§ÐµÐº-Ð»Ð¸ÑÑ â{serial} Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½.")
        await state.clear()
        return
    await message.answer(
        f"â ï¸ Ð£Ð´Ð°Ð»Ð¸ÑÑ ÑÐµÐº-Ð»Ð¸ÑÑ â{serial} Â«{cl['title']}Â»?",
        reply_markup=confirm_delete_kb("cl", str(serial))
    )
    await state.clear()


@router.callback_query(F.data.startswith("confirm_delete_cl_"))
async def delete_checklist_do(callback: CallbackQuery):
    serial = int(callback.data.split("_")[-1])
    fp = await db.delete_checklist(serial)
    if fp:
        delete_file(fp)
    await callback.message.edit_text(f"â Ð§ÐµÐº-Ð»Ð¸ÑÑ â{serial} ÑÐ´Ð°Ð»ÑÐ½.")
    await callback.answer()


@router.message(F.text == "ð§¹ ÐÑÐ¸ÑÑÐ¸ÑÑ Ð²ÑÐµ ÑÐµÐº-Ð»Ð¸ÑÑÑ")
@admin_only
async def clear_checklists_ask(message: Message):
    await message.answer(
        "â ï¸ ÐÑ ÑÐ¾ÑÐ½Ð¾ ÑÐ¾ÑÐ¸ÑÐµ ÑÐ´Ð°Ð»Ð¸ÑÑ <b>Ð²ÑÐµ ÑÐµÐº-Ð»Ð¸ÑÑÑ</b>?\nÐ­ÑÐ¾ Ð´ÐµÐ¹ÑÑÐ²Ð¸Ðµ Ð½ÐµÐ»ÑÐ·Ñ Ð¾ÑÐ¼ÐµÐ½Ð¸ÑÑ.",
        parse_mode="HTML",
        reply_markup=confirm_clear_kb("checklists")
    )


@router.callback_query(F.data == "confirm_clear_checklists")
async def clear_checklists_do(callback: CallbackQuery):
    paths = await db.clear_all_checklists()
    delete_files(paths)
    await callback.message.edit_text(f"â Ð£Ð´Ð°Ð»ÐµÐ½Ð¾ {len(paths)} ÑÐµÐº-Ð»Ð¸ÑÑÐ¾Ð².")
    await callback.answer()


# ââ CURATORS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

@router.message(F.text == "ð¥ ÐÑÑÐ°ÑÐ¾ÑÑ")
@admin_only
async def curators_menu(message: Message, state: FSMContext):
    await state.clear()
    curators = await db.get_all_curators()
    lines = ["ð¥ <b>ÐÑÑÐ°ÑÐ¾ÑÑ:</b>\n"]
    if curators:
        for c in curators:
            lines.append(f"â¢ {c['full_name']} (@{c['username'] or 'â'}, ID: {c['telegram_id']})")
    else:
        lines.append("ÐÑÑÐ°ÑÐ¾ÑÐ¾Ð² Ð¿Ð¾ÐºÐ° Ð½ÐµÑ.")
    lines.append("\nÐÑÐ¿ÑÐ°Ð²ÑÑÐµ /add_curator ÑÑÐ¾Ð±Ñ Ð´Ð¾Ð±Ð°Ð²Ð¸ÑÑ ÐºÑÑÐ°ÑÐ¾ÑÐ°.")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("add_curator"))
@admin_only
async def add_curator_start(message: Message, state: FSMContext):
    await state.set_state(AdminAddCurator.waiting_telegram_id)
    await message.answer(
        "ð¤ ÐÐ²ÐµÐ´Ð¸ÑÐµ Telegram ID Ð¸Ð»Ð¸ @username ÐºÑÑÐ°ÑÐ¾ÑÐ°:",
        reply_markup=cancel_kb()
    )


@router.message(AdminAddCurator.waiting_telegram_id)
async def add_curator_id(message: Message, state: FSMContext):
    text = message.text.strip()
    await state.update_data(curator_identifier=text)
    await state.set_state(AdminAddCurator.waiting_name)
    await message.answer("âï¸ ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð¸Ð¼Ñ ÐºÑÑÐ°ÑÐ¾ÑÐ° (Ð¤ÐÐ):")


@router.message(AdminAddCurator.waiting_name)
async def add_curator_name(message: Message, state: FSMContext, bot: Bot):
    full_name = message.text.strip()
    data = await state.get_data()
    identifier = data["curator_identifier"]

    tg_id = None
    username = None
    if identifier.startswith("@"):
        username = identifier.lstrip("@")
        await message.answer(
            "â ï¸ ÐÐ¾Ð¸ÑÐº Ð¿Ð¾ @username Ð½Ðµ Ð¿Ð¾Ð´Ð´ÐµÑÐ¶Ð¸Ð²Ð°ÐµÑÑÑ Telegram API.\n"
            "ÐÐ¾Ð¶Ð°Ð»ÑÐ¹ÑÑÐ°, Ð²Ð²ÐµÐ´Ð¸ÑÐµ ÑÐ¸ÑÐ»Ð¾Ð²Ð¾Ð¹ Telegram ID ÐºÑÑÐ°ÑÐ¾ÑÐ°.\n"
            "ÐÑÑÐ°ÑÐ¾Ñ Ð¼Ð¾Ð¶ÐµÑ ÑÐ·Ð½Ð°ÑÑ ÑÐ²Ð¾Ð¹ ID ÑÐµÑÐµÐ· @userinfobot"
        )
        await state.clear()
        return
    else:
        try:
            tg_id = int(identifier)
        except ValueError:
            await message.answer("â ÐÐµÐ²ÐµÑÐ½ÑÐ¹ ÑÐ¾ÑÐ¼Ð°Ñ ID.")
            await state.clear()
            return

    curator = await db.add_curator(tg_id, username, full_name)
    await state.clear()

    try:
        await bot.send_message(tg_id, "â ÐÐ°Ñ Ð´Ð¾Ð±Ð°Ð²Ð¸Ð»Ð¸ ÐºÐ°Ðº ÐºÑÑÐ°ÑÐ¾ÑÐ°.\nÐÑ Ð¼Ð¾Ð¶ÐµÑÐµ Ð²Ð¸Ð´ÐµÑÑ ÑÐ²Ð¾Ð¸Ñ ÑÑÐµÐ½Ð¸ÐºÐ¾Ð² Ð¸ Ð¿Ð¾Ð»ÑÑÐ°ÑÑ ÑÐ´Ð°Ð½Ð½ÑÐµ Ð Ð¢.")
    except Exception:
        pass

    await message.answer(
        f"â ÐÑÑÐ°ÑÐ¾Ñ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½:\n"
        f"ID: <code>{tg_id}</code>\n"
        f"ÐÐ¼Ñ: {full_name}",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )


# ââ GROUPS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

@router.message(F.text == "ð ÐÑÑÐ¿Ð¿Ñ")
@admin_only
async def groups_menu(message: Message, state: FSMContext):
    await state.clear()
    groups = await db.get_all_groups()
    lines = ["ð <b>ÐÑÐµ Ð³ÑÑÐ¿Ð¿Ñ:</b>\n"]
    if groups:
        for g in groups:
            curator = await db.get_curator_by_id(g["curator_id"])
            lines.append(f"â¢ {g['title']} (ÐºÑÑÐ°ÑÐ¾Ñ: {curator['full_name'] if curator else 'â'})")
    else:
        lines.append("ÐÑÑÐ¿Ð¿ Ð¿Ð¾ÐºÐ° Ð½ÐµÑ.")
    lines.append("\nÐÑÐ¿ÑÐ°Ð²ÑÑÐµ /add_group ÑÑÐ¾Ð±Ñ ÑÐ¾Ð·Ð´Ð°ÑÑ Ð³ÑÑÐ¿Ð¿Ñ.")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("add_group"))
@admin_only
async def add_group_start(message: Message, state: FSMContext):
    curators = await db.get_all_curators()
    if not curators:
        await message.answer("â Ð¡Ð½Ð°ÑÐ°Ð»Ð° Ð´Ð¾Ð±Ð°Ð²ÑÑÐµ ÐºÑÑÐ°ÑÐ¾ÑÐ°.")
        return
    lines = ["ÐÑÐ±ÐµÑÐ¸ÑÐµ ÐºÑÑÐ°ÑÐ¾ÑÐ° (Ð¾ÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð½Ð¾Ð¼ÐµÑ):\n"]
    for idx, c in enumerate(curators, 1):
        lines.append(f"{idx}. {c['full_name']}")
    await state.set_state(AdminAddGroup.waiting_curator)
    await state.update_data(curators=[dict(c) for c in curators])
    await message.answer("\n".join(lines), reply_markup=cancel_kb())


@router.message(AdminAddGroup.waiting_curator)
async def add_group_curator(message: Message, state: FSMContext):
    try:
        idx = int(message.text.strip()) - 1
    except ValueError:
        await message.answer("â ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð½Ð¾Ð¼ÐµÑ.")
        return
    data = await state.get_data()
    curators = data["curators"]
    if idx < 0 or idx >= len(curators):
        await message.answer("â ÐÐµÐ²ÐµÑÐ½ÑÐ¹ Ð½Ð¾Ð¼ÐµÑ.")
        return
    curator = curators[idx]
    await state.update_data(selected_curator_id=curator["id"], selected_curator_name=curator["full_name"])
    await state.set_state(AdminAddGroup.waiting_title)
    await message.answer(f"âï¸ ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð³ÑÑÐ¿Ð¿Ñ Ð´Ð»Ñ ÐºÑÑÐ°ÑÐ¾ÑÐ° {curator['full_name']}:")


@router.message(AdminAddGroup.waiting_title)
async def add_group_title(message: Message, state: FSMContext):
    title = message.text.strip()
    data = await state.get_data()
    group = await db.add_group(title, data["selected_curator_id"])
    await state.clear()
    await message.answer(
        f"â ÐÑÑÐ¿Ð¿Ð° Â«{title}Â» ÑÐ¾Ð·Ð´Ð°Ð½Ð° Ð´Ð»Ñ ÐºÑÑÐ°ÑÐ¾ÑÐ° {data['selected_curator_name']}.",
        reply_markup=admin_panel_kb()
    )


# ââ STUDENTS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

@router.message(F.text == "ð¨âð Ð£ÑÐµÐ½Ð¸ÐºÐ¸")
@admin_only
async def students_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "ð¨âð <b>Ð£Ð¿ÑÐ°Ð²Ð»ÐµÐ½Ð¸Ðµ ÑÑÐµÐ½Ð¸ÐºÐ°Ð¼Ð¸</b>\n\n"
        "ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ /add_student ÑÑÐ¾Ð±Ñ Ð´Ð¾Ð±Ð°Ð²Ð¸ÑÑ ÑÑÐµÐ½Ð¸ÐºÐ°.",
        parse_mode="HTML"
    )


@router.message(Command("add_student"))
@admin_only
async def add_student_start(message: Message, state: FSMContext):
    await state.set_state(AdminAddStudent.waiting_telegram_id)
    await message.answer("ð¤ ÐÐ²ÐµÐ´Ð¸ÑÐµ Telegram ID ÑÑÐµÐ½Ð¸ÐºÐ°:", reply_markup=cancel_kb())


@router.message(AdminAddStudent.waiting_telegram_id)
async def add_student_id(message: Message, state: FSMContext):
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("â ÐÐ²ÐµÐ´Ð¸ÑÐµ ÑÐ¸ÑÐ»Ð¾Ð²Ð¾Ð¹ Telegram ID.")
        return
    await state.update_data(student_tg_id=tg_id)
    await state.set_state(AdminAddStudent.waiting_name)
    await message.answer("âï¸ ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð¤ÐÐ ÑÑÐµÐ½Ð¸ÐºÐ°:")


@router.message(AdminAddStudent.waiting_name)
async def add_student_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    await state.update_data(student_full_name=full_name)
    curators = await db.get_all_curators()
    if not curators:
        await message.answer("â Ð¡Ð½Ð°ÑÐ°Ð»Ð° Ð´Ð¾Ð±Ð°Ð²ÑÑÐµ ÐºÑÑÐ°ÑÐ¾ÑÐ°.")
        await state.clear()
        return
    lines = ["ÐÑÐ±ÐµÑÐ¸ÑÐµ ÐºÑÑÐ°ÑÐ¾ÑÐ° (Ð½Ð¾Ð¼ÐµÑ):\n"]
    for idx, c in enumerate(curators, 1):
        lines.append(f"{idx}. {c['full_name']}")
    await state.update_data(curators=[dict(c) for c in curators])
    await state.set_state(AdminAddStudent.waiting_curator)
    await message.answer("\n".join(lines))


@router.message(AdminAddStudent.waiting_curator)
async def add_student_curator(message: Message, state: FSMContext):
    try:
        idx = int(message.text.strip()) - 1
    except ValueError:
        await message.answer("â ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð½Ð¾Ð¼ÐµÑ.")
        return
    data = await state.get_data()
    curators = data["curators"]
    if idx < 0 or idx >= len(curators):
        await message.answer("â ÐÐµÐ²ÐµÑÐ½ÑÐ¹ Ð½Ð¾Ð¼ÐµÑ.")
        return
    curator = curators[idx]
    await state.update_data(selected_curator_id=curator["id"], selected_curator_name=curator["full_name"])
    groups = await db.get_groups_by_curator(curator["id"])
    if not groups:
        await message.answer("â ï¸ Ð£ ÑÑÐ¾Ð³Ð¾ ÐºÑÑÐ°ÑÐ¾ÑÐ° Ð½ÐµÑ Ð³ÑÑÐ¿Ð¿. Ð£ÑÐµÐ½Ð¸Ðº Ð±ÑÐ´ÐµÑ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½ Ð±ÐµÐ· Ð³ÑÑÐ¿Ð¿Ñ.")
        data = await state.get_data()
        await _finish_add_student(message, state, data, None)
        return
    lines = ["ÐÑÐ±ÐµÑÐ¸ÑÐµ Ð³ÑÑÐ¿Ð¿Ñ (Ð½Ð¾Ð¼ÐµÑ) Ð¸Ð»Ð¸ 0 â Ð±ÐµÐ· Ð³ÑÑÐ¿Ð¿Ñ:\n"]
    for gidx, g in enumerate(groups, 1):
        lines.append(f"{gidx}. {g['title']}")
    await state.update_data(groups=[dict(g) for g in groups])
    await state.set_state(AdminAddStudent.waiting_group)
    await message.answer("\n".join(lines))


@router.message(AdminAddStudent.waiting_group)
async def add_student_group(message: Message, state: FSMContext, bot: Bot):
    try:
        idx = int(message.text.strip())
    except ValueError:
        await message.answer("â ÐÐ²ÐµÐ´Ð¸ÑÐµ Ð½Ð¾Ð¼ÐµÑ.")
        return
    data = await state.get_data()
    groups = data.get("groups", [])
    group_id = None
    if idx > 0:
        if idx > len(groups):
            await message.answer("â ÐÐµÐ²ÐµÑÐ½ÑÐ¹ Ð½Ð¾Ð¼ÐµÑ.")
            return
        group_id = groups[idx - 1]["id"]
    await _finish_add_student(message, state, data, group_id, bot)


async def _finish_add_student(message: Message, state: FSMContext, data: dict, group_id, bot: Bot = None):
    tg_id = data["student_tg_id"]
    full_name = data["student_full_name"]
    curator_id = data["selected_curator_id"]
    curator_name = data["selected_curator_name"]

    student = await db.add_student(tg_id, None, full_name, curator_id, group_id)
    await state.clear()

    if bot:
        try:
            await bot.send_message(
                tg_id,
                f"â ÐÐ°Ñ Ð´Ð¾Ð±Ð°Ð²Ð¸Ð» ÐºÑÑÐ°ÑÐ¾Ñ <b>{curator_name}</b>.\n"
                f"Ð¢ÐµÐ¿ÐµÑÑ Ð²Ñ Ð¼Ð¾Ð¶ÐµÑÐµ ÑÐ´Ð°Ð²Ð°ÑÑ ÑÐ°Ð±Ð¾ÑÐ¸Ðµ ÑÐµÑÑÐ°Ð´Ð¸ ÑÐµÑÐµÐ· ÑÐ°Ð·Ð´ÐµÐ» Â«ð¤ Ð¡Ð´Ð°ÑÑ Ð Ð¢Â».",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await message.answer(
        f"â Ð£ÑÐµÐ½Ð¸Ðº Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½:\nÐ¤ÐÐ: {full_name}\nID: <code>{tg_id}</code>\nÐÑÑÐ°ÑÐ¾Ñ: {curator_name}",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )


# ââ ACCESS MANAGEMENT ââââââââââââââââââââââââââââââââââââââââââââââââââââââ

@router.message(F.text == "ð ÐÐ¾ÑÑÑÐ¿")
@admin_only
async def access_menu(message: Message, state: FSMContext):
    await state.clear()
    users = await db.get_all_users_with_access()
    lines = [f"ð <b>ÐÐ¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ð¸ Ñ Ð´Ð¾ÑÑÑÐ¿Ð¾Ð¼:</b> {len(users)} ÑÐµÐ».\n"]
    for u in users[:20]:
        lines.append(f"â¢ {u['full_name']} (@{u['username'] or 'â'}, {u['telegram_id']})")
    lines.append("\n/grant_access â Ð²ÑÐ´Ð°ÑÑ Ð´Ð¾ÑÑÑÐ¿\n/revoke_access â Ð·Ð°Ð±ÑÐ°ÑÑ Ð´Ð¾ÑÑÑÐ¿")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("grant_access"))
@admin_only
async def grant_access_start(message: Message, state: FSMContext):
    await state.set_state(AdminGrantAccess.waiting_telegram_id)
    await message.answer("ÐÐ²ÐµÐ´Ð¸ÑÐµ Telegram ID Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ Ð´Ð»Ñ Ð²ÑÐ´Ð°ÑÐ¸ Ð´Ð¾ÑÑÑÐ¿Ð°:", reply_markup=cancel_kb())


@router.message(AdminGrantAccess.waiting_telegram_id)
async def grant_access_do(message: Message, state: FSMContext, bot: Bot):
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("â ÐÐ²ÐµÐ´Ð¸ÑÐµ ÑÐ¸ÑÐ»Ð¾Ð²Ð¾Ð¹ ID.")
        await state.clear()
        return
    await db.set_user_access(tg_id, True)
    await state.clear()
    try:
        await bot.send_message(tg_id, "â ÐÐ°Ð¼ Ð²ÑÐ´Ð°Ð½ Ð´Ð¾ÑÑÑÐ¿ Ðº ÑÐ°Ð±Ð¾ÑÐ¸Ð¼ ÑÐµÑÑÐ°Ð´ÑÐ¼ Ð¸ ÑÐµÐº-Ð»Ð¸ÑÑÐ°Ð¼!")
    except Exception:
        pass
    await message.answer(f"â ÐÐ¾ÑÑÑÐ¿ Ð²ÑÐ´Ð°Ð½ Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ <code>{tg_id}</code>.", parse_mode="HTML", reply_markup=admin_panel_kb())


@router.message(Command("revoke_access"))
@admin_only
async def revoke_access_start(message: Message, state: FSMContext):
    await state.set_state(AdminRevokeAccess.waiting_telegram_id)
    await message.answer("ÐÐ²ÐµÐ´Ð¸ÑÐµ Telegram ID Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ Ð´Ð»Ñ ÑÐ½ÑÑÐ¸Ñ Ð´Ð¾ÑÑÑÐ¿Ð°:", reply_markup=cancel_kb())


@router.message(AdminRevokeAccess.waiting_telegram_id)
async def revoke_access_do(message: Message, state: FSMContext):
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("â ÐÐ²ÐµÐ´Ð¸ÑÐµ ÑÐ¸ÑÐ»Ð¾Ð²Ð¾Ð¹ ID.")
        await state.clear()
        return
    await db.set_user_access(tg_id, False)
    await state.clear()
    await message.answer(f"â ÐÐ¾ÑÑÑÐ¿ ÑÐ½ÑÑ Ñ Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ <code>{tg_id}</code>.", parse_mode="HTML", reply_markup=admin_panel_kb())


# ââ CLEAR SUBMISSIONS ââââââââââââââââââââââââââââââââââââââââââââââââââââââ

@router.message(F.text == "ð§¹ ÐÑÐ¸ÑÑÐ¸ÑÑ ÑÐ´Ð°Ð½Ð½ÑÐµ Ð Ð¢")
@admin_only
async def clear_submissions_ask(message: Message):
    await message.answer(
        "â ï¸ ÐÑ ÑÐ¾ÑÐ½Ð¾ ÑÐ¾ÑÐ¸ÑÐµ ÑÐ´Ð°Ð»Ð¸ÑÑ <b>Ð²ÑÐµ ÑÐ´Ð°Ð½Ð½ÑÐµ Ð Ð¢</b>?\nÐ­ÑÐ¾ Ð´ÐµÐ¹ÑÑÐ²Ð¸Ðµ Ð½ÐµÐ»ÑÐ·Ñ Ð¾ÑÐ¼ÐµÐ½Ð¸ÑÑ.",
        parse_mode="HTML",
        reply_markup=confirm_clear_kb("submissions")
    )


@router.callback_query(F.data == "confirm_clear_submissions")
async def clear_submissions_do(callback: CallbackQuery):
    paths = await db.clear_all_submissions()
    from services.file_service import delete_files
    delete_files(paths)
    await callback.message.edit_text(f"â Ð£Ð´Ð°Ð»ÐµÐ½Ð¾ {len(paths)} Ð·Ð°Ð¿Ð¸ÑÐµÐ¹ ÑÐ´Ð°Ð½Ð½ÑÑ Ð Ð¢.")
    await callback.answer()


@router.callback_query(F.data == "cancel_clear")
async def cancel_clear(callback: CallbackQuery):
    await callback.message.edit_text("â ÐÑÐ¸ÑÑÐºÐ° Ð¾ÑÐ¼ÐµÐ½ÐµÐ½Ð°.")
    await callback.answer()


@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("â Ð£Ð´Ð°Ð»ÐµÐ½Ð¸Ðµ Ð¾ÑÐ¼ÐµÐ½ÐµÐ½Ð¾.")
    await callback.answer()


# ââ EXPORT âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

@router.message(F.text == "ð Ð­ÐºÑÐ¿Ð¾ÑÑ ÑÐ´Ð°Ñ")
@admin_only
async def export_submissions_start(message: Message):
    await message.answer(
        "ð ÐÑÐ±ÐµÑÐ¸ÑÐµ Ð¿ÐµÑÐ¸Ð¾Ð´ Ð´Ð»Ñ ÑÐºÑÐ¿Ð¾ÑÑÐ°:",
        reply_markup=period_filter_kb("export_subs")
    )


@router.callback_query(F.data.startswith("export_subs_"))
async def export_submissions_do(callback: CallbackQuery):
    period = callback.data.replace("export_subs_", "")
    submissions = await db.get_submissions(period=period)
    if not submissions:
        await callback.message.answer("ð ÐÐµÑ Ð´Ð°Ð½Ð½ÑÑ Ð·Ð° Ð²ÑÐ±ÑÐ°Ð½Ð½ÑÐ¹ Ð¿ÐµÑÐ¸Ð¾Ð´.")
        await callback.answer()
        return
    buf = export_submissions_xlsx(submissions)
    period_label = {"today": "ÑÐµÐ³Ð¾Ð´Ð½Ñ", "week": "Ð·Ð° Ð½ÐµÐ´ÐµÐ»Ñ", "month": "Ð·Ð° Ð¼ÐµÑÑÑ", "all": "Ð²ÑÐµ Ð²ÑÐµÐ¼Ñ"}.get(period, period)
    file = BufferedInputFile(buf.read(), filename=f"submissions_{period}.xlsx")
    await callback.message.answer_document(
        file,
        caption=f"ð <b>Ð­ÐºÑÐ¿Ð¾ÑÑ ÑÐ´Ð°Ñ Ð Ð¢</b>\nÐÐµÑÐ¸Ð¾Ð´: {period_label}\nÐÐ¾Ð»Ð¸ÑÐµÑÑÐ²Ð¾: {len(submissions)}",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.text == "ð¤ Ð­ÐºÑÐ¿Ð¾ÑÑ Ð·Ð°ÑÑÑÐ¾Ð²")
@admin_only
async def export_bookings_admin(message: Message):
    bookings = await db.get_all_bookings()
    if not bookings:
        await message.answer("ð ÐÐµÑ Ð·Ð°Ð¿Ð¸ÑÐµÐ¹ Ð½Ð° Ð·Ð°ÑÑÑÑ.")
        return
    buf = export_bookings_xlsx(bookings)
    file = BufferedInputFile(buf.read(), filename="exam_bookings.xlsx")
    await message.answer_document(file, caption=f"ð¤ <b>ÐÐ°Ð¿Ð¸ÑÐ¸ Ð½Ð° Ð·Ð°ÑÑÑÑ</b>\nÐÑÐµÐ³Ð¾: {len(bookings)}", parse_mode="HTML")
