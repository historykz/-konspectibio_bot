from config import ADMIN_ID


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def parse_identifier(arg: str) -> tuple[int | None, str | None]:
    """Парсит @username или telegram_id из строки."""
    arg = arg.strip()
    if not arg:
        return None, None
    if arg.startswith("@"):
        return None, arg
    if arg.isdigit():
        return int(arg), None
    # просто username без @
    return None, "@" + arg
