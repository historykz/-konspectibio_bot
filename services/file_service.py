import os
import shutil
import logging
from config import FILES_DIR, CHECKLISTS_DIR, TEMP_DIR

logger = logging.getLogger(__name__)


def get_temp_dir(student_telegram_id: int) -> str:
    d = os.path.join(TEMP_DIR, str(student_telegram_id))
    os.makedirs(d, exist_ok=True)
    return d


def clear_temp_dir(student_telegram_id: int):
    d = os.path.join(TEMP_DIR, str(student_telegram_id))
    if os.path.exists(d):
        shutil.rmtree(d)


def save_workbook_file(file_bytes: bytes, filename: str) -> str:
    os.makedirs(FILES_DIR, exist_ok=True)
    path = os.path.join(FILES_DIR, filename)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path


def save_checklist_file(file_bytes: bytes, filename: str) -> str:
    os.makedirs(CHECKLISTS_DIR, exist_ok=True)
    path = os.path.join(CHECKLISTS_DIR, filename)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path


def save_temp_photo(file_bytes: bytes, student_telegram_id: int, order_index: int) -> str:
    d = get_temp_dir(student_telegram_id)
    path = os.path.join(d, f"photo_{order_index:04d}.jpg")
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path


def delete_file(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.error(f"Failed to delete {path}: {e}")


def delete_files(paths: list[str]):
    for p in paths:
        delete_file(p)
