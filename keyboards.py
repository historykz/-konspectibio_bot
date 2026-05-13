from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def replace_note_keyboard(number: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Заменить",
                    callback_data=f"replace_note:{number}"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_replace"
                )
            ]
        ]
    )
