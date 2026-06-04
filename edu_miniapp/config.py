"""Конфигурация проекта. Читается из переменных окружения / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "").rstrip("/")

ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
]

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8080"))

DB_PATH: str = os.getenv("DB_PATH", "data/bot.db")

DEV_MODE: bool = os.getenv("DEV_MODE", "0") == "1"

# Папки на сервере (см. спецификацию)
FILES_DIR = BASE_DIR / "files"
CHECKLISTS_DIR = BASE_DIR / "checklists"
SUBMISSIONS_DIR = BASE_DIR / "submissions"
TEMP_DIR = BASE_DIR / "temp"
LOGS_DIR = BASE_DIR / "logs"

for _d in (FILES_DIR, CHECKLISTS_DIR, SUBMISSIONS_DIR, TEMP_DIR, LOGS_DIR):
    _d.mkdir(exist_ok=True)

# Папка БД
(BASE_DIR / DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def validate() -> None:
    """Проверка обязательных настроек при старте."""
    problems = []
    if not BOT_TOKEN:
        problems.append("BOT_TOKEN не задан")
    if not WEBAPP_URL and not DEV_MODE:
        problems.append("WEBAPP_URL не задан (нужен HTTPS-адрес мини-приложения)")
    if problems:
        raise RuntimeError("Ошибки конфигурации: " + "; ".join(problems))
