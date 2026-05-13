import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from utils import ensure_files_dir, logger

from handlers import admin, user


async def main():
    init_db()
    ensure_files_dir()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin.router)
    dp.include_router(user.router)

    logger.info("Бот запущен")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
