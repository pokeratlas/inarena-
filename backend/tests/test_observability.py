from __future__ import annotations

import importlib
import io
import logging
import json

from fastapi.testclient import TestClient


def load_app(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "observability.sqlite3"))
    monkeypatch.setenv("INARENA_ENV", "test")
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.setenv("INARENA_RELEASE", "test-release-123")
    monkeypatch.delenv("INARENA_DATABASE_URL", raising=False)
    monkeypatch.delenv("INARENA_REDIS_URL", raising=False)
    monkeypatch.delenv("INARENA_ENABLE_LEGACY_API", raising=False)

    import app.db as db
    import app.main as main

    importlib.reload(db)
    importlib.reload(main)
    return main


def test_request_id_and_release_metadata(tmp_path, monkeypatch):
    main = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        version = client.get(
            "/version",
            headers={"X-Request-ID": "req-release-1"},
        )
        assert version.status_code == 200
        assert version.headers["X-Request-ID"] == "req-release-1"
        assert version.json() == {
            "release": "test-release-123",
            "environment": "test",
        }

        missing = client.get(
            "/api/v1/tables/does-not-exist",
            headers={"X-Request-ID": "req-error-1"},
        )
        assert missing.status_code == 404
        assert missing.headers["X-Request-ID"] == "req-error-1"

        invalid = client.get(
            "/health",
            headers={"X-Request-ID": "bad request id with spaces"},
        )
        assert invalid.status_code == 200
        replacement = invalid.headers["X-Request-ID"]
        assert replacement != "bad request id with spaces"
        assert len(replacement) == 32


def test_operator_diagnostics_contract(tmp_path, monkeypatch):
    main = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        denied = client.get("/api/v1/operator/diagnostics")
        assert denied.status_code == 401

        response = client.get(
            "/api/v1/operator/diagnostics",
            headers={"X-Operator-Key": "operator"},
        )
        assert response.status_code == 200
        body = response.json()

        assert body["release"]["release"] == "test-release-123"
        assert body["database"]["backend"] == "sqlite"
        assert body["database"]["schema_version"] >= 14
        assert body["database"]["pool"] is None
        assert body["realtime"]["local_websocket_connections"] == 0
        assert body["realtime"]["local_websocket_tables"] == 0
        assert body["realtime"]["outbox_backlog"] >= 0
        assert body["realtime"]["coordination"]["configured"] is False


def test_structured_request_log_excludes_sensitive_headers(
    tmp_path,
    monkeypatch,
):
    main = load_app(tmp_path, monkeypatch)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    main.logger.handlers[:] = [handler]
    main.logger.setLevel(logging.INFO)

    with TestClient(main.app) as client:
        response = client.get(
            "/health",
            headers={
                "X-Request-ID": "req-safe-log",
                "X-Session-ID": "secret-session-value",
                "X-Operator-Key": "secret-operator-value",
                "Authorization": "Bearer secret-auth-value",
            },
        )
        assert response.status_code == 200

    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    assert lines
    payload = json.loads(lines[-1])

    assert payload["event"] == "http_request"
    assert payload["request_id"] == "req-safe-log"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status"] == 200
    assert isinstance(payload["duration_ms"], (int, float))

    serialized = stream.getvalue()
    assert "secret-session-value" not in serialized
    assert "secret-operator-value" not in serialized
    assert "secret-auth-value" not in serialized
