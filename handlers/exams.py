import logging
from datetime import datetime, timedelta, date
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from keyboards import cancel_kb, slots_kb, cancel_booking_kb, main_menu_kb
from states import CuratorCreateSlots, StudentBookSlot
from services.access_service import is_curator, is_admin, get_role

logger = logging.getLogger(__name__)
router = Router()


def generate_slots(start: str, end: str, duration: int) -> list[str]:
    """Generate time slots between start and end with given duration in minutes."""
    fmt = "%H:%M"
    current = datetime.strptime(start, fmt)
    end_dt = datetime.strptime(end, fmt)
    slots = []
    while current < end_dt:
        slots.append(current.strftime(fmt))
        current += timedelta(minutes=duration)
    return slots


# ── CURATOR: CREATE SLOTS ───────────────────────────────────────────────────

@router.message(F.text == "🗓 Создать слоты для зачёта")
async def create_slots_start(message: Message, state: FSMContext):
    curator = await db.get_curator_by_telegram_id(message.from_user.id)
    if not curator and not await is_admin(message.from_user.id):
        await message.answer("⛔ Только кураторы могут создавать слоты.")
        return
    await state.set_state(CuratorCreateSlots.waiting_date)
    await state.update_data(curator_id=curator["id"] if curator else None)
    await message.answer(
        "📅 Введите дату в формате <code>ДД.ММ.ГГГГ</code>:\nПример: <code>24.06.2026</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@router.message(CuratorCreateSlots.waiting_date)
async def create_slots_date(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        d = datetime.strptime(text, "%d.%m.%Y")
        date_str = d.strftime("%Y-%m-%d")
    except ValueError:
        await message.answer("❌ Неверный формат. Введите дату как <code>24.06.2026</code>", parse_mode="HTML")
        return
    await state.update_data(date=date_str, date_display=text)
    await state.set_state(CuratorCreateSlots.waiting_start_time)
    await message.answer("🕐 Введите время начала (ЧЧ:ММ):\nПример: <code>14:00</code>", parse_mode="HTML")


@router.message(CuratorCreateSlots.waiting_start_time)
async def create_slots_start_time(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат. Введите время как <code>14:00</code>", parse_mode="HTML")
        return
    await state.update_data(start_time=text)
    await state.set_state(CuratorCreateSlots.waiting_end_time)
    await message.answer("🕔 Введите время окончания (ЧЧ:ММ):\nПример: <code>16:00</code>", parse_mode="HTML")


@router.message(CuratorCreateSlots.waiting_end_time)
async def create_slots_end_time(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат. Введите время как <code>16:00</code>", parse_mode="HTML")
        return
    await state.update_data(end_time=text)
    await state.set_state(CuratorCreateSlots.waiting_duration)
    await message.answer("⏱ Длительность одного зачёта в минутах (по умолчанию 15):\nПример: <code>15</code>", parse_mode="HTML")


@router.message(CuratorCreateSlots.waiting_duration)
async def create_slots_duration(message: Message, state: FSMContext):
    try:
        duration = int(message.text.strip())
        if duration < 5:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число минут (минимум 5).")
        return
    await state.update_data(duration=duration)
    await state.set_state(CuratorCreateSlots.waiting_meet_link)
    await message.answer("🔗 Введите ссылку Google Meet:")


@router.message(CuratorCreateSlots.waiting_meet_link)
async def create_slots_meet(message: Message, state: FSMContext):
    meet_link = message.text.strip()
    data = await state.get_data()
    slots = generate_slots(data["start_time"], data["end_time"], data["duration"])

    if not slots:
        await message.answer("❌ Не удалось создать слоты. Проверьте время начала и окончания.")
        await state.clear()
        return

    count = await db.add_exam_slots(
        data["curator_id"], data["date"], slots, data["duration"], meet_link
    )
    await state.clear()

    slots_preview = "\n".join(slots[:5])
    if len(slots) > 5:
        slots_preview += f"\n...и ещё {len(slots) - 5}"

    await message.answer(
        f"✅ <b>Создано {count} слотов</b>\n\n"
        f"📅 Дата: {data['date_display']}\n"
        f"🔗 Meet: {meet_link}\n\n"
        f"Слоты:\n{slots_preview}",
        parse_mode="HTML"
    )


# ── STUDENT: BOOK SLOT ──────────────────────────────────────────────────────

@router.message(F.text == "🗓 Запись на зачёт")
async def exam_booking_start(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    student = await db.get_student_by_telegram_id(tg_id)

    if not student:
        await message.answer("⛔ Вы не прикреплены к куратору. Обратитесь к администратору.")
        return

    # Check if already booked
    existing = await db.get_student_active_booking(student["id"])
    if existing:
        cancel_time_ok = True
        try:
            slot_dt = datetime.strptime(f"{existing['date']} {existing['slot_time']}", "%Y-%m-%d %H:%M")
            if (slot_dt - datetime.now()).total_seconds() < 3600:
                cancel_time_ok = False
        except Exception:
            pass

        await message.answer(
            f"✅ У вас уже есть запись на зачёт:\n\n"
            f"📅 Дата: {existing['date']}\n"
            f"🕒 Время: {existing['slot_time']}\n"
            f"🔗 Meet: {existing.get('google_meet_link') or existing.get('slot_meet', '—')}",
            reply_markup=cancel_booking_kb(existing["id"]) if cancel_time_ok else None
        )
        return

    slots = await db.get_free_slots_for_curator(student["curator_id"])
    if not slots:
        await message.answer("😔 Свободных слотов пока нет. Ожидайте, когда куратор добавит время.")
        return

    await state.set_state(StudentBookSlot.waiting_full_name)
    await state.update_data(student_id=student["id"], curator_id=student["curator_id"],
                            group_id=student.get("group_id"))
    await message.answer(
        "📝 Введите ваше ФИО для записи на зачёт:",
        reply_markup=cancel_kb()
    )


@router.message(StudentBookSlot.waiting_full_name)
async def exam_booking_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("❌ Введите полное ФИО.")
        return
    data = await state.get_data()
    await state.update_data(full_name=full_name)
    await state.set_state(StudentBookSlot.choosing_slot)

    slots = await db.get_free_slots_for_curator(data["curator_id"])
    if not slots:
        await message.answer("😔 Слоты закончились.")
        await state.clear()
        return

    await message.answer(
        f"🗓 <b>Доступное время для зачёта:</b>",
        parse_mode="HTML",
        reply_markup=slots_kb(slots)
    )


@router.callback_query(F.data.startswith("book_slot_"), StudentBookSlot.choosing_slot)
async def exam_book_slot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    slot_id = int(callback.data.split("_")[-1])
    data = await state.get_data()

    slot = await db.get_slot_by_id(slot_id)
    if not slot or slot["is_booked"]:
        await callback.answer("❌ Этот слот уже занят!", show_alert=True)
        return

    booked = await db.book_slot(slot_id, data["student_id"])
    if not booked:
        await callback.answer("❌ Слот занят, выберите другой.", show_alert=True)
        return

    booking = await db.create_booking(
        slot_id, data["student_id"], data["curator_id"],
        data.get("group_id"), data["full_name"], slot["google_meet_link"] or ""
    )

    await state.clear()

    curator = await db.get_curator_by_id(data["curator_id"])
    date_display = slot["date"]
    try:
        date_display = datetime.strptime(slot["date"], "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        pass

    await callback.message.answer(
        f"✅ <b>Вы записались на зачёт!</b>\n\n"
        f"📅 Дата: {date_display}\n"
        f"🕒 Время: {slot['slot_time']}\n"
        f"👨‍🏫 Куратор: {curator['full_name'] if curator else '—'}\n"
        f"🔗 Meet: {slot['google_meet_link'] or '—'}",
        parse_mode="HTML",
        reply_markup=cancel_booking_kb(booking["id"])
    )

    # Notify curator
    if curator:
        student = await db.get_student_by_telegram_id(callback.from_user.id)
        group = await db.get_group_by_id(data.get("group_id")) if data.get("group_id") else None
        try:
            await bot.send_message(
                curator["telegram_id"],
                f"🗓 <b>Новая запись на зачёт</b>\n\n"
                f"👨‍🎓 Ученик: <b>{data['full_name']}</b>\n"
                f"Username: @{student['username'] if student and student.get('username') else '—'}\n"
                f"Группа: {group['title'] if group else '—'}\n"
                f"📅 Дата: {date_display}\n"
                f"🕒 Время: {slot['slot_time']}\n"
                f"🔗 Meet: {slot['google_meet_link'] or '—'}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify curator: {e}")

    await callback.answer()


# ── CANCEL BOOKING ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cancel_booking_"))
async def cancel_booking_handler(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    # Find booking
    student = await db.get_student_by_telegram_id(tg_id)
    is_adm = await is_admin(tg_id)
    cur = await db.get_curator_by_telegram_id(tg_id)

    # Get slot info to check time
    from database import get_db
    async with await get_db() as dbc:
        rows = await dbc.execute_fetchall(
            """SELECT b.*, s.date, s.slot_time FROM exam_bookings b
               JOIN exam_slots s ON b.slot_id=s.id WHERE b.id=?""",
            (booking_id,)
        )
    if not rows:
        await callback.answer("❌ Запись не найдена.", show_alert=True)
        return
    booking_row = dict(rows[0])

    # Time check for students
    if not is_adm and not cur:
        try:
            slot_dt = datetime.strptime(f"{booking_row['date']} {booking_row['slot_time']}", "%Y-%m-%d %H:%M")
            if (slot_dt - datetime.now()).total_seconds() < 3600:
                await callback.answer("⛔ Отменить запись уже нельзя. До зачёта осталось меньше 1 часа.", show_alert=True)
                return
        except Exception:
            pass

    cancelled = await db.cancel_booking(booking_id)
    if cancelled:
        await callback.message.edit_text("✅ Запись на зачёт отменена. Слот освобождён.")
    else:
        await callback.answer("❌ Не удалось отменить.", show_alert=True)
    await callback.answer()


# ── SCHEDULER: NOTIFICATIONS ────────────────────────────────────────────────

async def check_exam_notifications(bot: Bot):
    """Called periodically by APScheduler to send exam reminders."""
    try:
        bookings = await db.get_upcoming_bookings_for_notifications()
        now = datetime.now()

        for b in bookings:
            try:
                slot_dt = datetime.strptime(f"{b['date']} {b['slot_time']}", "%Y-%m-%d %H:%M")
            except Exception:
                continue

            diff_minutes = (slot_dt - now).total_seconds() / 60

            # 10 minute reminder
            if 9 <= diff_minutes <= 11 and not b.get("notified_10_min"):
                date_display = slot_dt.strftime("%d.%m.%Y")
                meet = b.get("slot_meet") or b.get("google_meet_link", "—")

                try:
                    await bot.send_message(
                        b["student_telegram_id"],
                        f"⏳ <b>Через 10 минут зачёт!</b>\n\n"
                        f"👨‍🏫 Куратор: {b['curator_name']}\n"
                        f"📅 Дата: {date_display}\n"
                        f"🕒 Время: {b['slot_time']}\n"
                        f"🔗 Meet: {meet}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"10min notify student error: {e}")

                try:
                    await bot.send_message(
                        b["curator_telegram_id"],
                        f"⏳ <b>Через 10 минут зачёт!</b>\n\n"
                        f"👨‍🎓 Ученик: {b['student_full_name']}\n"
                        f"Группа: {b.get('group_title', '—')}\n"
                        f"🕒 Время: {b['slot_time']}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"10min notify curator error: {e}")

                await db.mark_notified(b["id"], "10min")

            # Start notification
            elif -1 <= diff_minutes <= 1 and not b.get("notified_start"):
                date_display = slot_dt.strftime("%d.%m.%Y")
                meet = b.get("slot_meet") or b.get("google_meet_link", "—")

                try:
                    await bot.send_message(
                        b["student_telegram_id"],
                        f"⏰ <b>Время зачёта пришло!</b>\n\n"
                        f"👨‍🏫 Куратор: {b['curator_name']}\n"
                        f"📅 Дата: {date_display}\n"
                        f"🕒 Время: {b['slot_time']}\n\n"
                        f"🔗 Ссылка на Google Meet:\n{meet}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Start notify student error: {e}")

                try:
                    await bot.send_message(
                        b["curator_telegram_id"],
                        f"⏰ <b>Время зачёта пришло!</b>\n\n"
                        f"👨‍🎓 Ученик: {b['student_full_name']}\n"
                        f"Username: @{b.get('student_username') or '—'}\n"
                        f"Группа: {b.get('group_title', '—')}\n"
                        f"📅 Дата: {date_display}\n"
                        f"🕒 Время: {b['slot_time']}\n\n"
                        f"🔗 Google Meet:\n{meet}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Start notify curator error: {e}")

                await db.mark_notified(b["id"], "start")

    except Exception as e:
        logger.error(f"Notification check error: {e}", exc_info=True)
