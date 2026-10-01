from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def reload_app(tmp_path, monkeypatch, environment: str):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "ready.sqlite3"))
    monkeypatch.setenv("INARENA_ENV", environment)

    import app.db as db
    import app.main as main

    importlib.reload(db)
    importlib.reload(main)
    return main


def test_ready_in_development_with_database(tmp_path, monkeypatch):
    monkeypatch.delenv("INARENA_DATABASE_URL", raising=False)
    main = reload_app(tmp_path, monkeypatch, "development")

    with TestClient(main.app) as client:
        response = client.get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["checks"]["database"] == "ok"
        assert body["checks"]["schema_version"] >= 13


def test_production_readiness_requires_database_url_and_operator_key(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("INARENA_DATABASE_URL", raising=False)
    monkeypatch.delenv("INARENA_OPERATOR_KEY", raising=False)
    monkeypatch.delenv("INARENA_ENABLE_LEGACY_API", raising=False)

    main = reload_app(tmp_path, monkeypatch, "production")

    with TestClient(main.app) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        detail = response.json()["detail"]
        missing = detail["checks"]["configuration"]["missing_or_invalid"]
        assert "INARENA_DATABASE_URL" in missing
        assert "INARENA_OPERATOR_KEY" in missing


def test_production_readiness_rejects_legacy_api(tmp_path, monkeypatch):
    monkeypatch.delenv("INARENA_DATABASE_URL", raising=False)
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")

    main = reload_app(tmp_path, monkeypatch, "production")

    with TestClient(main.app) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        detail = response.json()["detail"]
        invalid = detail["checks"]["configuration"]["missing_or_invalid"]
        assert "INARENA_ENABLE_LEGACY_API must be disabled" in invalid
