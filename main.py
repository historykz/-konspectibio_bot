import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
from database import init_db
from handlers import user, admin, submissions, curator, exams

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in .env!")
        sys.exit(1)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Register routers (order matters for priority)
    dp.include_router(user.router)
    dp.include_router(admin.router)
    dp.include_router(curator.router)
    dp.include_router(exams.router)
    dp.include_router(submissions.router)  # Last â has generic number handler

    # APScheduler for exam notifications
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        exams.check_exam_notifications,
        "interval",
        minutes=1,
        args=[bot],
        id="exam_notifications",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started")

    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
