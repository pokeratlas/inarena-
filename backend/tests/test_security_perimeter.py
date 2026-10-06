from __future__ import annotations

import importlib

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def load_app(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "security.sqlite3"))
    monkeypatch.setenv("INARENA_ENV", "test")
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.setenv(
        "INARENA_ALLOWED_ORIGINS",
        "https://app.example",
    )
    monkeypatch.delenv("INARENA_DATABASE_URL", raising=False)
    monkeypatch.delenv("INARENA_REDIS_URL", raising=False)
    monkeypatch.delenv("INARENA_ENABLE_LEGACY_API", raising=False)

    import app.db as db
    import app.security as security
    import app.main as main

    importlib.reload(db)
    importlib.reload(security)
    importlib.reload(main)
    return main


def test_security_headers_and_cors_allowlist(tmp_path, monkeypatch):
    main = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.headers["X-Content-Type-Options"] == "nosniff"
        assert health.headers["Referrer-Policy"] == "no-referrer"
        assert "camera=()" in health.headers["Permissions-Policy"]

        allowed = client.options(
            "/api/v1/tables",
            headers={
                "Origin": "https://app.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert allowed.status_code == 200
        assert (
            allowed.headers["Access-Control-Allow-Origin"]
            == "https://app.example"
        )

        denied = client.options(
            "/api/v1/tables",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "Access-Control-Allow-Origin" not in denied.headers


def test_request_body_limit_returns_413_with_request_id(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("INARENA_MAX_REQUEST_BODY_BYTES", "1024")
    main = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/operator/tables",
            headers={
                "X-Operator-Key": "operator",
                "X-Request-ID": "body-limit-1",
            },
            json={"name": "x" * 5000},
        )

    assert response.status_code == 413
    assert response.headers["X-Request-ID"] == "body-limit-1"
    assert response.json()["request_id"] == "body-limit-1"


def test_operator_rate_limit_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_RATE_LIMIT_OPERATOR_PER_MINUTE", "1")
    main = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        first = client.get(
            "/api/v1/operator/diagnostics",
            headers={
                "X-Operator-Key": "operator",
                "X-Request-ID": "rate-1",
            },
        )
        second = client.get(
            "/api/v1/operator/diagnostics",
            headers={
                "X-Operator-Key": "operator",
                "X-Request-ID": "rate-2",
            },
        )
        public = client.get("/health")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["X-Request-ID"] == "rate-2"
    assert second.json()["request_id"] == "rate-2"
    assert public.status_code == 200


def test_websocket_origin_and_connection_rate_limit(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("INARENA_RATE_LIMIT_WS_PER_MINUTE", "1")
    main = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        created = client.post(
            "/api/v1/operator/tables",
            headers={"X-Operator-Key": "operator"},
            json={"name": "WS security"},
        )
        assert created.status_code == 201
        table_id = created.json()["id"]

        try:
            with client.websocket_connect(
                f"/ws/tables/{table_id}",
                headers={"Origin": "https://evil.example"},
            ):
                raise AssertionError("disallowed origin connected")
        except WebSocketDisconnect as exc:
            assert exc.code == 4403

        with client.websocket_connect(
            f"/ws/tables/{table_id}",
            headers={"Origin": "https://app.example"},
        ) as socket:
            snapshot = socket.receive_json()
            assert snapshot["type"] == "table_snapshot"

        try:
            with client.websocket_connect(
                f"/ws/tables/{table_id}",
                headers={"Origin": "https://app.example"},
            ):
                raise AssertionError("rate-limited websocket connected")
        except WebSocketDisconnect as exc:
            assert exc.code == 4429
