import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMINS: list[int] = [int(x.strip()) for x in os.getenv("ADMINS", "").split(",") if x.strip()]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(BASE_DIR, "files")
CHECKLISTS_DIR = os.path.join(BASE_DIR, "checklists")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
SUBMISSIONS_DIR = os.path.join(BASE_DIR, "submissions")
DB_PATH = os.path.join(BASE_DIR, "bot.db")

for d in [FILES_DIR, CHECKLISTS_DIR, TEMP_DIR, SUBMISSIONS_DIR]:
    os.makedirs(d, exist_ok=True)
