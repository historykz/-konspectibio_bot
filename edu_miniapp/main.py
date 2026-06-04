"""Точка входа. Одновременно запускает:
  • polling бота (aiogram)
  • веб-сервер (aiohttp) — фронтенд мини-приложения + API
  • планировщик (APScheduler) — напоминания о зачётах
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from bot import handlers
from bot import journal_import
from database import db, repo
from webapp.server import create_app


def setup_logging() -> None:
    config.LOGS_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.LOGS_DIR / "bot.log", encoding="utf-8"),
        ],
    )


async def check_exam_reminders(bot: Bot) -> None:
    """Каркас задачи планировщика: каждую минуту проверять зачёты.
    Здесь будет логика напоминаний за 10 минут и в момент начала."""
    # TODO: выбрать брони, у которых пора слать напоминание, и разослать.
    pass


async def main() -> None:
    setup_logging()
    config.validate()

    await db.init_db()
    await repo.ensure_admins(config.ADMIN_IDS)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(handlers.router)
    dp.include_router(journal_import.router)

    await handlers.setup_menu_button(bot)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_exam_reminders, "interval", minutes=1, args=[bot])
    scheduler.start()

    app = create_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.HOST, config.PORT)
    await site.start()
    logging.info("Веб-сервер запущен на http://%s:%s", config.HOST, config.PORT)

    try:
        logging.info("Бот запущен (polling)")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await runner.cleanup()
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Остановлено")
