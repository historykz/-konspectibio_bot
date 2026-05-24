from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def main_menu_kb(role: str = "user") -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📚 Рабочие тетради"))
    builder.row(KeyboardButton(text="✅ Чек-листы"))
    builder.row(KeyboardButton(text="📤 Сдать РТ"))
    builder.row(KeyboardButton(text="🗓 Запись на зачёт"))
    builder.row(KeyboardButton(text="👤 Мой профиль"))
    if role in ("admin",):
        builder.row(KeyboardButton(text="⚙️ Админ-панель"))
    if role in ("curator", "admin"):
        builder.row(KeyboardButton(text="👥 Мои группы"))
        builder.row(KeyboardButton(text="📋 Список сдавших РТ"))
    return builder.as_markup(resize_keyboard=True)


def admin_panel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="➕ Добавить РТ"),
        KeyboardButton(text="📚 Список РТ"),
    )
    builder.row(
        KeyboardButton(text="🗑 Удалить РТ"),
        KeyboardButton(text="🧹 Очистить все РТ"),
    )
    builder.row(
        KeyboardButton(text="✅ Управление чек-листами"),
    )
    builder.row(
        KeyboardButton(text="👥 Кураторы"),
        KeyboardButton(text="👨‍🎓 Ученики"),
    )
    builder.row(
        KeyboardButton(text="📋 Группы"),
        KeyboardButton(text="🔑 Доступ"),
    )
    builder.row(
        KeyboardButton(text="🧹 Очистить сданные РТ"),
        KeyboardButton(text="📊 Экспорт сдач"),
    )
    builder.row(
        KeyboardButton(text="📤 Экспорт зачётов"),
    )
    builder.row(KeyboardButton(text="🏠 Главное меню"))
    return builder.as_markup(resize_keyboard=True)


def checklist_admin_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="➕ Добавить чек-лист"),
        KeyboardButton(text="📋 Список чек-листов"),
    )
    builder.row(
        KeyboardButton(text="🗑 Удалить чек-лист"),
        KeyboardButton(text="🧹 Очистить все чек-листы"),
    )
    builder.row(KeyboardButton(text="◀️ Назад в админ-панель"))
    return builder.as_markup(resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def submit_photo_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📄 Отправить в виде PDF", callback_data="submit_pdf"))
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data="submit_cancel"))
    return builder.as_markup()


def confirm_clear_kb(action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, очистить", callback_data=f"confirm_clear_{action}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_clear"),
    )
    return builder.as_markup()


def confirm_delete_kb(item_type: str, item_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{item_type}_{item_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete"),
    )
    return builder.as_markup()


def curator_panel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="👥 Мои группы"))
    builder.row(KeyboardButton(text="📋 Список сдавших РТ"))
    builder.row(KeyboardButton(text="➕ Добавить ученика"))
    builder.row(KeyboardButton(text="➕ Создать группу"))
    builder.row(KeyboardButton(text="🗓 Создать слоты для зачёта"))
    builder.row(KeyboardButton(text="📊 Мои записи на зачёт"))
    builder.row(KeyboardButton(text="📤 Экспорт сдач"))
    builder.row(KeyboardButton(text="📤 Экспорт зачётов"))
    builder.row(KeyboardButton(text="🏠 Главное меню"))
    return builder.as_markup(resize_keyboard=True)


def period_filter_kb(prefix: str = "filter") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Сегодня", callback_data=f"{prefix}_today"),
        InlineKeyboardButton(text="📆 За неделю", callback_data=f"{prefix}_week"),
    )
    builder.row(
        InlineKeyboardButton(text="🗓 За месяц", callback_data=f"{prefix}_month"),
        InlineKeyboardButton(text="📂 Все время", callback_data=f"{prefix}_all"),
    )
    return builder.as_markup()


def slots_kb(slots: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    current_date = None
    for slot in slots:
        if slot["date"] != current_date:
            current_date = slot["date"]
        builder.row(
            InlineKeyboardButton(
                text=f"📅 {slot['date']} {slot['slot_time']}",
                callback_data=f"book_slot_{slot['id']}"
            )
        )
    return builder.as_markup()


def cancel_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="❌ Отменить запись",
        callback_data=f"cancel_booking_{booking_id}"
    ))
    return builder.as_markup()
