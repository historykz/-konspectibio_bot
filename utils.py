import os
import logging
from config import FILES_DIR, ADMIN_ID


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)


def ensure_files_dir():
    os.makedirs(FILES_DIR, exist_ok=True)


def is_admin(user_id: int):
    return user_id == ADMIN_ID


def is_valid_number(text: str):
    return text.isdigit() and int(text) > 0


def normalize_student_value(value: str):
    value = value.strip()

    if value.startswith("@"):
        return value

    if value.isdigit():
        return value

    raise ValueError("Введите ID или @username")
