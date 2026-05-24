import logging
import os
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

import database as db
from config import ADMINS
from keyboards import main_menu_kb, admin_panel_kb, curator_panel_kb, cancel_kb
from services.access_service import get_role, has_access, is_admin, is_curator

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    tg = message.from_user
    user = await db.get_or_create_user(tg.id, tg.username, tg.full_name)

    # Sync role
    if tg.id in ADMINS:
        await db.set_user_role(tg.id, "admin")
        role = "admin"
    else:
        role = await get_role(tg.id)

    await message.answer(
        f"👋 Привет, <b>{tg.full_name}</b>!\n\n"
        f"Выберите раздел из меню ниже:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(role)
    )


@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    role = await get_role(message.from_user.id)
    await message.answer("✅ Действие отменено.", reply_markup=main_menu_kb(role))


@router.message(F.text == "🏠 Главное меню")
async def go_home(message: Message, state: FSMContext):
    await state.clear()
    role = await get_role(message.from_user.id)
    await message.answer("🏠 Главное меню", reply_markup=main_menu_kb(role))


@router.message(F.text == "👤 Мой профиль")
async def my_profile(message: Message):
    tg = message.from_user
    role = await get_role(tg.id)
    user = await db.get_user(tg.id)

    role_label = {
        "admin": "⚙️ Администратор",
        "curator": "👨‍🏫 Куратор",
        "student": "👨‍🎓 Ученик",
        "user_with_access": "✅ Пользователь с доступом",
        "user": "👤 Пользователь",
    }.get(role, "👤 Пользователь")

    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"Имя: <b>{tg.full_name}</b>\n"
        f"Username: @{tg.username or '—'}\n"
        f"ID: <code>{tg.id}</code>\n"
        f"Роль: {role_label}\n"
    )

    if role == "student":
        student = await db.get_student_by_telegram_id(tg.id)
        if student:
            curator = await db.get_curator_by_id(student["curator_id"])
            group = await db.get_group_by_id(student["group_id"]) if student.get("group_id") else None
            text += f"Куратор: <b>{curator['full_name'] if curator else '—'}</b>\n"
            text += f"Группа: <b>{group['title'] if group else '—'}</b>\n"

    access = await has_access(tg.id)
    text += f"Доступ к РТ: {'✅' if access else '❌'}\n"

    await message.answer(text, parse_mode="HTML")


# ── WORKBOOKS ──────────────────────────────────────────────────────────────

@router.message(F.text == "📚 Рабочие тетради")
async def workbooks_section(message: Message, state: FSMContext):
    await state.clear()
    if not await has_access(message.from_user.id):
        await message.answer(
            "⛔ У вас пока нет доступа к рабочим тетрадям.\n"
            "Обратитесь к своему куратору или администратору."
        )
        return

    books = await db.get_all_workbooks()
    if not books:
        await message.answer("📚 Рабочих тетрадей пока нет.")
        return

    lines = ["📚 <b>Доступные рабочие тетради:</b>\n"]
    for b in books:
        lines.append(f"№{b['serial_number']} — {b['title']}")
    lines.append("\nЧтобы получить файл, отправьте номер:\nНапример: <code>1</code>")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text.regexp(r"^\d+$"))
async def handle_serial_number(message: Message, state: FSMContext):
    from aiogram.fsm.context import FSMContext
    current = await state.get_state()
    # Don't intercept if user is in any FSM state
    if current is not None:
        return

    serial = int(message.text.strip())

    # Try workbooks first if user has access
    if await has_access(message.from_user.id):
        wb = await db.get_workbook_by_serial(serial)
        if wb:
            if not os.path.exists(wb["file_path"]):
                await message.answer("❌ Файл не найден на сервере. Обратитесь к администратору.")
                return
            file = FSInputFile(wb["file_path"])
            await message.answer_document(
                file,
                caption=f"📘 <b>Рабочая тетрадь №{wb['serial_number']}</b>\nТема: {wb['title']}",
                parse_mode="HTML"
            )
            return

    await message.answer(f"❌ Рабочая тетрадь с номером <b>{serial}</b> не найдена.", parse_mode="HTML")


# ── CHECKLISTS ─────────────────────────────────────────────────────────────

@router.message(F.text == "✅ Чек-листы")
async def checklists_section(message: Message, state: FSMContext):
    await state.clear()
    if not await has_access(message.from_user.id):
        await message.answer(
            "⛔ У вас пока нет доступа к чек-листам.\n"
            "Обратитесь к куратору или администратору."
        )
        return

    items = await db.get_all_checklists()
    if not items:
        await message.answer("✅ Чек-листов пока нет.")
        return

    lines = ["✅ <b>Доступные чек-листы:</b>\n"]
    for c in items:
        lines.append(f"№{c['serial_number']} — {c['title']}")
    lines.append("\nЧтобы получить чек-лист, отправьте номер:\nНапример: <code>1</code>")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "⚙️ Админ-панель")
async def open_admin_panel_btn(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    await state.clear()
    await message.answer("⚙️ <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_panel_kb())


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    await state.clear()
    await message.answer("⚙️ <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_panel_kb())


@router.message(F.text == "👥 Мои группы")
async def curator_groups_btn(message: Message):
    from services.access_service import is_curator as _is_curator, is_admin as _is_admin
    tg_id = message.from_user.id

    if await _is_admin(tg_id):
        groups = await db.get_all_groups()
        if not groups:
            await message.answer("📋 Групп пока нет.")
            return
        lines = ["📋 <b>Все группы:</b>\n"]
        for g in groups:
            curator = await db.get_curator_by_id(g["curator_id"])
            lines.append(f"• {g['title']} (куратор: {curator['full_name'] if curator else '—'})")
        await message.answer("\n".join(lines), parse_mode="HTML")
        return

    curator = await db.get_curator_by_telegram_id(tg_id)
    if not curator:
        await message.answer("⛔ У вас нет доступа к этому разделу.")
        return

    groups = await db.get_groups_by_curator(curator["id"])
    if not groups:
        await message.answer("👥 У вас пока нет групп.")
        return

    lines = ["📋 <b>Ваши группы:</b>\n"]
    for idx, g in enumerate(groups, 1):
        lines.append(f"{idx}. {g['title']}")
    lines.append("\nОтправьте номер группы, чтобы увидеть учеников.")

    await message.answer("\n".join(lines), parse_mode="HTML")
