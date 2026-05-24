from config import ADMINS
import database as db


async def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMINS


async def is_curator(telegram_id: int) -> bool:
    curator = await db.get_curator_by_telegram_id(telegram_id)
    return curator is not None


async def is_student(telegram_id: int) -> bool:
    student = await db.get_student_by_telegram_id(telegram_id)
    return student is not None


async def has_access(telegram_id: int) -> bool:
    if await is_admin(telegram_id):
        return True
    user = await db.get_user(telegram_id)
    return bool(user and user.get("has_access"))


async def get_role(telegram_id: int) -> str:
    if telegram_id in ADMINS:
        return "admin"
    curator = await db.get_curator_by_telegram_id(telegram_id)
    if curator:
        return "curator"
    student = await db.get_student_by_telegram_id(telegram_id)
    if student:
        return "student"
    user = await db.get_user(telegram_id)
    if user and user.get("has_access"):
        return "user_with_access"
    return "user"
