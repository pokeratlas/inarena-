from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def load_app(tmp_path, monkeypatch, environment="development", origins=""):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "security.sqlite3"))
    monkeypatch.setenv("INARENA_ENV", environment)
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.setenv("INARENA_ALLOWED_ORIGINS", origins)
    monkeypatch.delenv("INARENA_DATABASE_URL", raising=False)
    monkeypatch.delenv("INARENA_REDIS_URL", raising=False)
    monkeypatch.delenv("INARENA_ENABLE_LEGACY_API", raising=False)

    import app.db as db
    import app.main as main

    importlib.reload(db)
    importlib.reload(main)
    return main


def test_security_headers_are_present(tmp_path, monkeypatch):
    main = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["Permissions-Policy"] == (
            "camera=(), microphone=(), geolocation=()"
        )
        assert response.headers["Cache-Control"] == "no-store"
        assert "Strict-Transport-Security" not in response.headers


def test_production_adds_hsts(tmp_path, monkeypatch):
    main = load_app(tmp_path, monkeypatch, environment="production")

    with TestClient(main.app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers["Strict-Transport-Security"] == (
            "max-age=31536000; includeSubDomains"
        )


def test_cors_allows_only_configured_origin(tmp_path, monkeypatch):
    main = load_app(
        tmp_path,
        monkeypatch,
        origins="https://app.example.com,https://operator.example.com",
    )

    with TestClient(main.app) as client:
        allowed = client.options(
            "/api/v1/tables",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert allowed.status_code == 200
        assert allowed.headers["Access-Control-Allow-Origin"] == (
            "https://app.example.com"
        )

        denied = client.options(
            "/api/v1/tables",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "Access-Control-Allow-Origin" not in denied.headers


def test_production_readiness_rejects_wildcard_cors(tmp_path, monkeypatch):
    main = load_app(
        tmp_path,
        monkeypatch,
        environment="production",
        origins="*",
    )

    with TestClient(main.app) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        detail = response.json()["detail"]
        invalid = detail["checks"]["configuration"]["missing_or_invalid"]
        assert "INARENA_ALLOWED_ORIGINS must not contain wildcard" in invalid
