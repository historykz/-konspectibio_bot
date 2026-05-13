import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import admin, user

def setup_logging() -> None:
logging.basicConfig(
level=logging.INFO,
format=”%(asctime)s | %(levelname)-7s | %(name)s | %(message)s”,
stream=sys.stdout,
)
# Чуть тише от сторонних библиотек
logging.getLogger(“aiogram.event”).setLevel(logging.WARNING)

async def main() -> None:
setup_logging()
logger = logging.getLogger(“bot”)

```
await init_db()

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=MemoryStorage())

# Порядок важен: сначала админский роутер (с middleware-фильтром по ADMIN_ID),
# затем пользовательский.
dp.include_router(admin.router)
dp.include_router(user.router)

me = await bot.get_me()
logger.info("Бот запущен: @%s (id=%s)", me.username, me.id)

try:
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
finally:
    await bot.session.close()
```

if **name** == “**main**”:
try:
asyncio.run(main())
except (KeyboardInterrupt, SystemExit):
pass
