"""Хендлеры бота. Главная задача — запустить мини-приложение и
обработать сервисные команды. Вся UI-логика живёт во фронтенде."""
import logging

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

import config
from database import repo

log = logging.getLogger(__name__)
router = Router()


def _webapp_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🚀 Открыть приложение",
                web_app=WebAppInfo(url=config.WEBAPP_URL),
            )
        ]]
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    await repo.upsert_user(user.id, user.username, user.first_name)

    profile = await repo.get_profile(user.id)
    if profile and profile["has_access"]:
        text = "Добро пожаловать! Открывайте приложение для работы."
    else:
        text = (
            "Здравствуйте! Доступ к материалам пока не открыт. "
            "Обратитесь к куратору или администратору.\n\n"
            "Когда доступ появится — открывайте приложение кнопкой ниже."
        )
    await message.answer(text, reply_markup=_webapp_kb())


@router.message(Command("app"))
async def cmd_app(message: Message) -> None:
    await message.answer("Открыть приложение:", reply_markup=_webapp_kb())


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>")


async def setup_menu_button(bot: Bot) -> None:
    """Кнопка-меню слева от поля ввода открывает мини-приложение."""
    if not config.WEBAPP_URL:
        log.warning("WEBAPP_URL не задан — кнопка меню не установлена")
        return
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Приложение",
            web_app=WebAppInfo(url=config.WEBAPP_URL),
        )
    )
