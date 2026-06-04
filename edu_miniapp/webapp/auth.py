"""Проверка Telegram WebApp initData.

Telegram подписывает initData ключом, производным от токена бота.
Сервер обязан проверять подпись — иначе любой сможет подделать telegram_id.
Алгоритм: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import config

# Сколько секунд initData считается свежим (защита от повторного использования)
MAX_AGE_SECONDS = 24 * 60 * 60


def validate_init_data(init_data: str) -> dict | None:
    """Вернуть данные пользователя {id, username, first_name, ...} или None."""
    if not init_data:
        return None

    # DEV-режим: пропускаем проверку (initData можно подставить вручную в браузере)
    if config.DEV_MODE:
        try:
            parsed = dict(parse_qsl(init_data))
            user = json.loads(parsed.get("user", "{}")) if parsed.get("user") else {}
            return user or None
        except (ValueError, json.JSONDecodeError):
            return None

    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    calc_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        return None

    # Проверка свежести
    auth_date = parsed.get("auth_date")
    if auth_date and auth_date.isdigit():
        if time.time() - int(auth_date) > MAX_AGE_SECONDS:
            return None

    try:
        user = json.loads(parsed.get("user", "{}")) if parsed.get("user") else {}
    except json.JSONDecodeError:
        return None
    return user or None
