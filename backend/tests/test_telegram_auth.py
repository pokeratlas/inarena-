from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient


BOT_TOKEN = "123456:test-token"


def signed_init_data(user: dict, auth_date: int | None = None) -> str:
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAE-test",
        "user": json.dumps(user, separators=(",", ":"), ensure_ascii=False),
    }
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(fields.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()
    fields["hash"] = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(fields)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "telegram.sqlite3"))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as test_client:
        yield test_client


def test_valid_telegram_init_data_creates_persisted_session(client):
    init_data = signed_init_data(
        {"id": 12345, "first_name": "Test", "username": "player"}
    )
    response = client.post(
        "/api/v1/auth/telegram",
        json={"init_data": init_data},
    )
    assert response.status_code == 201
    session = response.json()
    assert session["user_id"] == "tg:12345"
    assert session["provider"] == "telegram"
    assert session["data"]["telegram_user"]["username"] == "player"

    restored = client.get(f"/api/v1/sessions/{session['session_id']}")
    assert restored.status_code == 200
    assert restored.json()["user_id"] == "tg:12345"


def test_tampered_telegram_init_data_is_rejected(client):
    init_data = signed_init_data({"id": 12345, "first_name": "Test"})
    tampered = init_data.replace("12345", "99999")

    response = client.post(
        "/api/v1/auth/telegram",
        json={"init_data": tampered},
    )
    assert response.status_code == 401


def test_expired_telegram_init_data_is_rejected(client):
    init_data = signed_init_data(
        {"id": 12345, "first_name": "Test"},
        auth_date=int(time.time()) - 7200,
    )
    response = client.post(
        "/api/v1/auth/telegram",
        json={"init_data": init_data},
    )
    assert response.status_code == 401
