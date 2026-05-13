import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DATABASE_PATH = "bot.db"
FILES_DIR = "files"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в .env")

if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID не найден в .env")
