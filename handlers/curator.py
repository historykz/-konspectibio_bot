import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

import database as db
from keyboards import (
    curator_panel_kb, cancel_kb, period_filter_kb, main_menu_kb
)
from states import CuratorAddStudent, CuratorAddGroup
from services.export_service import export_submissions_xlsx, export_bookings_xlsx
from services.access_service import is_curator, is_admin

logger = logging.getLogger(__name__)
router = Router()


async def curator_required(message: Message) -> dict | None:
    curator = await db.get_curator_by_telegram_id(message.from_user.id)
    if not curator and not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этому разделу.")
        return None
    return curator


# ── SUBMISSIONS LIST ────────────────────────────────────────────────────────

@router.message(F.text == "📋 Список сдавших РТ")
async def submissions_list_start(message: Message):
    tg_id = message.from_user.id
    is_adm = await is_admin(tg_id)
    curator = await db.get_curator_by_telegram_id(tg_id)

    if not is_adm and not curator:
        await message.answer("⛔ Нет доступа.")
        return

    await message.answer(
        "📋 <b>Список сдавших РТ</b>\nВыберите период:",
        parse_mode="HTML",
        reply_markup=period_filter_kb("subs_list")
    )


@router.callback_query(F.data.startswith("subs_list_"))
async def submissions_list_show(callback: CallbackQuery):
    period = callback.data.replace("subs_list_", "")
    tg_id = callback.from_user.id
    is_adm = await is_admin(tg_id)
    curator = await db.get_curator_by_telegram_id(tg_id)

    curator_id = None if is_adm else (curator["id"] if curator else None)
    submissions = await db.get_submissions(curator_id=curator_id, period=period)

    if not submissions:
        await callback.message.answer("📋 Нет записей за выбранный период.")
        await callback.answer()
        return

    lines = [f"📋 <b>Сданные РТ ({len(submissions)}):</b>\n"]
    for idx, s in enumerate(submissions[:20], 1):
        dt_str = s.get("submitted_at", "")
        date_part, time_part = "—", "—"
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str)
                date_part = dt.strftime("%d.%m.%Y")
                time_part = dt.strftime("%H:%M")
            except Exception:
                pass
        lines.append(
            f"{idx}. <b>{s.get('student_full_name', '—')}</b>\n"
            f"   Группа: {s.get('group_title', '—')}\n"
            f"   Дата: {date_part}, Время: {time_part}\n"
            f"   Куратор: {s.get('curator_name', '—')}"
        )

    if len(submissions) > 20:
        lines.append(f"\n<i>...и ещё {len(submissions) - 20} записей. Используйте экспорт для полного списка.</i>")

    await callback.message.answer("\n\n".join(lines), parse_mode="HTML")
    await callback.answer()


# ── CURATOR: ADD STUDENT ────────────────────────────────────────────────────

@router.message(F.text == "➕ Добавить ученика")
async def curator_add_student_start(message: Message, state: FSMContext):
    curator = await curator_required(message)
    if not curator:
        return
    await state.set_state(CuratorAddStudent.waiting_telegram_id)
    await state.update_data(curator_id=curator["id"], curator_name=curator["full_name"])
    await message.answer("👤 Введите Telegram ID ученика:", reply_markup=cancel_kb())


@router.message(CuratorAddStudent.waiting_telegram_id)
async def curator_add_student_id(message: Message, state: FSMContext):
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите числовой ID.")
        return
    await state.update_data(student_tg_id=tg_id)
    await state.set_state(CuratorAddStudent.waiting_name)
    await message.answer("✏️ Введите ФИО ученика:")


@router.message(CuratorAddStudent.waiting_name)
async def curator_add_student_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    await state.update_data(student_full_name=full_name)
    data = await state.get_data()
    groups = await db.get_groups_by_curator(data["curator_id"])
    if not groups:
        await _finish_curator_add_student(message, state, data, None)
        return
    lines = ["Выберите группу (номер) или 0 — без группы:\n"]
    for idx, g in enumerate(groups, 1):
        lines.append(f"{idx}. {g['title']}")
    await state.update_data(groups=[dict(g) for g in groups])
    await state.set_state(CuratorAddStudent.waiting_group)
    await message.answer("\n".join(lines))


@router.message(CuratorAddStudent.waiting_group)
async def curator_add_student_group(message: Message, state: FSMContext, bot: Bot):
    try:
        idx = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите номер.")
        return
    data = await state.get_data()
    groups = data.get("groups", [])
    group_id = None
    if idx > 0:
        if idx > len(groups):
            await message.answer("❌ Неверный номер.")
            return
        group_id = groups[idx - 1]["id"]
    await _finish_curator_add_student(message, state, data, group_id, bot)


async def _finish_curator_add_student(message: Message, state: FSMContext, data: dict, group_id, bot: Bot = None):
    tg_id = data["student_tg_id"]
    full_name = data["student_full_name"]
    curator_id = data["curator_id"]
    curator_name = data["curator_name"]

    await db.add_student(tg_id, None, full_name, curator_id, group_id)
    await state.clear()

    if bot:
        try:
            await bot.send_message(
                tg_id,
                f"✅ Вас добавил куратор <b>{curator_name}</b>.\n"
                f"Теперь вы можете сдавать рабочие тетради через раздел «📤 Сдать РТ».",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await message.answer(
        f"✅ Ученик добавлен:\n{full_name} (ID: {tg_id})",
        reply_markup=curator_panel_kb()
    )


# ── CURATOR: CREATE GROUP ───────────────────────────────────────────────────

@router.message(F.text == "➕ Создать группу")
async def curator_create_group_start(message: Message, state: FSMContext):
    curator = await curator_required(message)
    if not curator:
        return
    await state.set_state(CuratorAddGroup.waiting_title)
    await state.update_data(curator_id=curator["id"])
    await message.answer("✏️ Введите название группы:", reply_markup=cancel_kb())


@router.message(CuratorAddGroup.waiting_title)
async def curator_create_group_title(message: Message, state: FSMContext):
    title = message.text.strip()
    data = await state.get_data()
    group = await db.add_group(title, data["curator_id"])
    await state.clear()
    await message.answer(f"✅ Группа «{title}» создана.", reply_markup=curator_panel_kb())


# ── CURATOR: EXPORT ─────────────────────────────────────────────────────────

@router.message(F.text == "📤 Экспорт сдач")
async def curator_export_subs(message: Message):
    is_adm = await is_admin(message.from_user.id)
    curator = await db.get_curator_by_telegram_id(message.from_user.id)
    if not is_adm and not curator:
        await message.answer("⛔ Нет доступа.")
        return

    curator_id = None if is_adm else curator["id"]
    submissions = await db.get_submissions(curator_id=curator_id, period="all")
    if not submissions:
        await message.answer("📊 Нет данных для экспорта.")
        return
    buf = export_submissions_xlsx(submissions)
    file = BufferedInputFile(buf.read(), filename="my_submissions.xlsx")
    await message.answer_document(
        file,
        caption=f"📊 Экспорт сдач РТ. Всего: {len(submissions)}",
    )


@router.message(F.text == "📊 Мои записи на зачёт")
async def curator_exam_bookings(message: Message):
    curator = await db.get_curator_by_telegram_id(message.from_user.id)
    is_adm = await is_admin(message.from_user.id)
    if not curator and not is_adm:
        await message.answer("⛔ Нет доступа.")
        return

    curator_id = None if is_adm else curator["id"]
    bookings = await db.get_all_bookings(curator_id=curator_id)
    if not bookings:
        await message.answer("🗓 Записей на зачёты нет.")
        return

    lines = [f"🗓 <b>Записи на зачёт ({len(bookings)}):</b>\n"]
    for b in bookings[:15]:
        lines.append(
            f"• <b>{b.get('student_full_name', '—')}</b> — {b.get('date', '?')} {b.get('slot_time', '?')}\n"
            f"  Статус: {b.get('status', '—')} | Группа: {b.get('group_title', '—')}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")
