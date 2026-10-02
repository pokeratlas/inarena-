from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def reload_app(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "observability.sqlite3"))
    monkeypatch.setenv("INARENA_ENV", "test")
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator-secret")
    monkeypatch.setenv("INARENA_RELEASE", "test-release")

    import app.db as db
    import app.main as main

    importlib.reload(db)
    importlib.reload(main)
    return main


def test_request_id_is_echoed_and_present_in_error_body(tmp_path, monkeypatch):
    main = reload_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        response = client.get(
            "/api/v1/auth/session",
            headers={"X-Request-ID": "req-test-123"},
        )

    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == "req-test-123"
    assert response.json()["request_id"] == "req-test-123"


def test_invalid_request_id_is_replaced(tmp_path, monkeypatch):
    main = reload_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        response = client.get(
            "/health",
            headers={"X-Request-ID": "unsafe request id with spaces"},
        )

    assert response.status_code == 200
    generated = response.headers["X-Request-ID"]
    assert generated
    assert generated != "unsafe request id with spaces"


def test_release_metadata_contract(tmp_path, monkeypatch):
    main = reload_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        response = client.get("/release")

    assert response.status_code == 200
    assert response.json() == {
        "release": "test-release",
        "environment": "test",
    }


def test_operator_diagnostics_exposes_runtime_without_secrets(
    tmp_path,
    monkeypatch,
):
    main = reload_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        response = client.get(
            "/api/v1/operator/diagnostics",
            headers={"X-Operator-Key": "operator-secret"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["release"] == "test-release"
    assert body["database_backend"] == "sqlite"
    assert body["schema_version"] >= 14
    assert body["websocket"]["local_connections"] == 0
    assert isinstance(body["realtime_outbox"]["pending"], int)

    serialized = response.text
    assert "operator-secret" not in serialized
    assert "X-Session-ID" not in serialized
