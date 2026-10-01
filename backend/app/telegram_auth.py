from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl


class TelegramAuthError(RuntimeError):
    pass


def validate_init_data(init_data: str, max_age_seconds: int = 3600) -> dict:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise TelegramAuthError("telegram auth is not configured")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    pairs.pop("signature", None)
    if not received_hash:
        raise TelegramAuthError("telegram hash is missing")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(pairs.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramAuthError("invalid telegram signature")

    auth_date_raw = pairs.get("auth_date")
    if not auth_date_raw:
        raise TelegramAuthError("telegram auth_date is missing")
    try:
        auth_date = int(auth_date_raw)
    except ValueError as exc:
        raise TelegramAuthError("invalid telegram auth_date") from exc

    now = int(time.time())
    if auth_date > now + 30 or now - auth_date > max_age_seconds:
        raise TelegramAuthError("telegram init data is expired")

    user_raw = pairs.get("user")
    if not user_raw:
        raise TelegramAuthError("telegram user is missing")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise TelegramAuthError("invalid telegram user") from exc

    if not isinstance(user, dict) or "id" not in user:
        raise TelegramAuthError("telegram user id is missing")

    return {
        "user": user,
        "auth_date": auth_date,
        "query_id": pairs.get("query_id"),
        "start_param": pairs.get("start_param"),
    }
