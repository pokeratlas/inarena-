from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def chat(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "chat.sqlite3"))
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")
    from app import db, service, main
    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)
    with TestClient(main.app) as client:
        table = client.post("/api/v1/tables", json={"name": "Chat"}).json()["id"]
        sessions = []
        for index in range(3):
            session = client.post("/api/v1/sessions", json={"user_id": f"chat-{index}", "provider": "test", "data": {}}).json()["session_id"]
            sessions.append({"X-Session-ID": session})
            if index < 2:
                assert client.post(f"/api/v1/tables/{table}/join-auth", headers=sessions[-1], json={"seat_no": index + 1, "stack": 1000}).status_code == 200
        yield client, f"/api/v1/tables/{table}/chat", sessions


def test_chat_identity_history_idempotency_and_throttle(chat):
    client, url, sessions = chat
    message = {"text": "  Привет <script>alert(1)</script>  ", "client_message_id": "first"}
    first = client.post(url, headers=sessions[0], json=message)
    assert first.status_code == 201
    assert first.json()["player_id"] == "chat-0"
    assert first.json()["text"] == message["text"].strip()
    assert client.post(url, headers=sessions[0], json=message).json() == first.json()
    assert client.post(url, headers=sessions[0], json={**message, "text": "different"}).status_code == 409
    throttled = client.post(url, headers=sessions[0], json={**message, "client_message_id": "second"})
    assert throttled.status_code == 429
    assert throttled.headers["Retry-After"] == "2"
    assert client.get(url, headers=sessions[1]).json() == [first.json()]
    assert client.post(url, headers=sessions[1], json={"text": "Ответ", "client_message_id": "reply"}).status_code == 201
    assert len(client.get(url, headers=sessions[0]).json()) == 2


def test_chat_access_and_validation(chat):
    client, url, sessions = chat
    body = {"text": "Hello", "client_message_id": "one"}
    for method in (client.get, client.post):
        payload = {"json": body} if method == client.post else {}
        assert method(url, **payload).status_code == 401
        assert method(url, headers=sessions[2], **payload).status_code == 403
    for text in ("", "   ", "x" * 501, "hello\x00"):
        assert client.post(url, headers=sessions[0], json={**body, "text": text}).status_code == 422
    from app.db import transaction
    with transaction() as conn:
        conn.execute("UPDATE auth_sessions SET expires_at = '2000-01-01T00:00:00+00:00' WHERE session_id = ?", (sessions[0]["X-Session-ID"],))
    assert client.get(url, headers=sessions[0]).status_code == 401
    with transaction() as conn:
        conn.execute("DELETE FROM runtime_seats WHERE player_id = 'chat-1'")
    assert client.get(url, headers=sessions[1]).status_code == 403


def test_chat_other_table_closed_and_bounded_history(chat):
    client, url, sessions = chat
    from app.db import transaction
    other = client.post("/api/v1/tables", json={"name": "Other"}).json()["id"]
    assert client.get(f"/api/v1/tables/{other}/chat", headers=sessions[0]).status_code == 403
    table_id = url.split("/")[-2]
    with transaction() as conn:
        for index in range(205):
            conn.execute("INSERT INTO table_chat (table_id, player_id, display_name, text, client_message_id, created_at) VALUES (?, 'chat-0', 'Player', ?, ?, '2026-10-04')", (table_id, str(index), str(index)))
    history = client.get(url, headers=sessions[1]).json()
    assert len(history) == 50
    assert [message["text"] for message in history] == [str(index) for index in range(155, 205)]
    assert client.post(url, headers=sessions[0], json={"text": "Latest", "client_message_id": "latest"}).status_code == 201
    with transaction() as conn:
        assert conn.execute("SELECT COUNT(*) AS total FROM table_chat WHERE table_id = ?", (table_id,)).fetchone()["total"] == 200
        conn.execute("UPDATE runtime_tables SET status = 'closed' WHERE id = ?", (table_id,))
    assert client.get(url, headers=sessions[0]).status_code == 409
    assert client.post(url, headers=sessions[0], json={"text": "Closed", "client_message_id": "closed"}).status_code == 409


def test_chat_upgrade_preserves_existing_seats(chat):
    client, url, sessions = chat
    from app.db import connect, ensure_schema
    conn = connect()
    conn.execute("DROP TABLE table_chat")
    conn.execute("DROP TABLE chat_senders")
    conn.execute("PRAGMA user_version = 16")
    conn.commit()
    conn.close()
    ensure_schema()
    assert client.get(url, headers=sessions[0]).json() == []
    assert client.post(url, headers=sessions[0], json={"text": "After upgrade", "client_message_id": "upgrade"}).status_code == 201
