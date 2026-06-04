"""Отправка уведомлений пользователям. Каркас: одна общая функция +
готовые шаблоны под события из спецификации."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

log = logging.getLogger(__name__)


async def notify(bot: Bot, telegram_id: int, text: str) -> bool:
    """Безопасная отправка (не падаем, если пользователь заблокировал бота)."""
    try:
        await bot.send_message(telegram_id, text)
        return True
    except TelegramAPIError as e:
        log.warning("Не удалось отправить уведомление %s: %s", telegram_id, e)
        return False


# --- Шаблоны событий (подключаются по мере реализации функций) ---

async def notify_added_to_group(bot: Bot, student_id: int, group_name: str) -> None:
    await notify(
        bot, student_id,
        f"✅ Вас добавили в группу «{group_name}». Доступ к материалам открыт.",
    )


async def notify_access_granted(bot: Bot, user_id: int) -> None:
    await notify(bot, user_id, "🔑 Вам открыт доступ к учебным материалам.")


async def notify_access_revoked(bot: Bot, user_id: int) -> None:
    await notify(bot, user_id, "⛔️ Доступ к учебным материалам отозван.")


async def notify_made_curator(bot: Bot, user_id: int) -> None:
    await notify(
        bot, user_id,
        "👨‍🏫 Вас назначили куратором. Откройте приложение — появились "
        "разделы управления группами, приёма работ и расписания зачётов.",
    )


async def notify_made_admin(bot: Bot, user_id: int) -> None:
    await notify(bot, user_id, "👑 Вам выданы права администратора.")
