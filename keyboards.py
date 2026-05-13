from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def replace_confirm_kb(number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Заменить", callback_data=f"replace:yes:{number}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="replace:no"),
        ]
    ])
