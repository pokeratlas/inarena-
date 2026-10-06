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


def signed_init_data(
    user: dict, auth_date: int | None = None, signature: str | None = None,
) -> str:
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAE-test",
        "user": json.dumps(user, separators=(",", ":"), ensure_ascii=False),
    }
    if signature is not None:
        fields["signature"] = signature
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


def test_modern_telegram_signature_field_is_included_in_bot_token_hash(client):
    init_data = signed_init_data(
        {"id": 12345, "first_name": "Test"}, signature="test-ed25519-signature",
    )
    response = client.post("/api/v1/auth/telegram", json={"init_data": init_data})
    assert response.status_code == 201
    assert response.json()["user_id"] == "tg:12345"


def test_signature_field_tampering_is_rejected(client):
    init_data = signed_init_data(
        {"id": 12345, "first_name": "Test"}, signature="test-ed25519-signature",
    )
    response = client.post(
        "/api/v1/auth/telegram",
        json={"init_data": init_data.replace("test-ed25519-signature", "tampered")},
    )
    assert response.status_code == 401


def test_rejection_diagnostics_exclude_credentials_and_user_data(client, monkeypatch):
    import app.main as main
    entries = []
    monkeypatch.setattr(main, "structured_log", lambda logger, event, **fields: entries.append({"event": event, **fields}))
    init_data = signed_init_data({"id": 12345, "first_name": "PRIVATE_NAME"})
    response = client.post(
        "/api/v1/auth/telegram",
        json={"init_data": init_data.replace("PRIVATE_NAME", "TAMPERED")},
        headers={"X-Request-ID": "telegram-auth-regression"},
    )
    assert response.status_code == 401
    assert len(entries) == 1
    assert entries[0]["reason"] == "hash_mismatch"
    assert entries[0]["request_id"] == "telegram-auth-regression"
    assert set(entries[0]) == {"event", "reason", "request_id", "release", "environment"}
    serialized = json.dumps(entries)
    for private_value in [BOT_TOKEN, init_data, "PRIVATE_NAME", "TAMPERED", "12345"]:
        assert private_value not in serialized


def test_unknown_validation_error_has_only_generic_log_reason():
    from app.telegram_auth import TelegramAuthError
    assert TelegramAuthError("sensitive arbitrary message").reason == "validation_failed"
