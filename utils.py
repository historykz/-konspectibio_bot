import logging
from typing import Optional

from config import ADMIN_ID

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def parse_identifier(token: str) -> tuple[Optional[int], Optional[str]]:
    """
    Принимает строку вроде '123456789' или '@username'.
    Возвращает (telegram_id, username). Один из них всегда None.
    """
    token = token.strip()
    if not token:
        return None, None
    if token.startswith("@"):
        return None, token[1:].lower()
    if token.isdigit():
        return int(token), None
    # username без @
    return None, token.lower()
