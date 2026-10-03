from __future__ import annotations

import hashlib
import importlib
import sqlite3
import time

from fastapi.testclient import TestClient


def load_app(tmp_path, monkeypatch):
    db_path = tmp_path / "operator-sessions.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))
    monkeypatch.setenv("INARENA_ENV", "test")
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "bootstrap-secret")
    monkeypatch.delenv("INARENA_DATABASE_URL", raising=False)
    monkeypatch.delenv("INARENA_ENABLE_LEGACY_API", raising=False)

    import app.db as db
    import app.main as main

    importlib.reload(db)
    importlib.reload(main)
    return main, db_path


def test_read_scope_can_read_but_cannot_write(tmp_path, monkeypatch):
    main, db_path = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        auth = client.post(
            "/api/v1/operator/auth",
            headers={"X-Operator-Key": "bootstrap-secret"},
            json={"scopes": ["operator:read"]},
        )
        assert auth.status_code == 200
        session = auth.json()
        token = session["token"]
        assert token.startswith("ops_")
        assert session["scopes"] == ["operator:read"]

        dashboard = client.get(
            "/api/v1/operator/dashboard",
            headers={"X-Operator-Key": token},
        )
        assert dashboard.status_code == 200

        write = client.post(
            "/api/v1/operator/balance",
            headers={"X-Operator-Key": token},
            json={"user_id": "p1", "delta": 100},
        )
        assert write.status_code == 401

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT token_hash FROM operator_sessions"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == hashlib.sha256(token.encode()).hexdigest()
        assert token not in rows[0][0]
    finally:
        conn.close()


def test_default_session_can_write_and_revoke_itself(tmp_path, monkeypatch):
    main, _ = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        auth = client.post(
            "/api/v1/operator/auth",
            headers={"X-Operator-Key": "bootstrap-secret"},
            json={"scopes": []},
        )
        assert auth.status_code == 200
        token = auth.json()["token"]

        write = client.post(
            "/api/v1/operator/balance",
            headers={"X-Operator-Key": token},
            json={"user_id": "p1", "delta": 100},
        )
        assert write.status_code == 200

        revoked = client.post(
            "/api/v1/operator/auth/revoke",
            headers={"X-Operator-Key": token},
        )
        assert revoked.status_code == 204

        denied = client.get(
            "/api/v1/operator/dashboard",
            headers={"X-Operator-Key": token},
        )
        assert denied.status_code == 401


def test_expired_operator_session_is_rejected(tmp_path, monkeypatch):
    main, db_path = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        auth = client.post(
            "/api/v1/operator/auth",
            headers={"X-Operator-Key": "bootstrap-secret"},
            json={"scopes": ["operator:read"]},
        )
        token = auth.json()["token"]

        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "UPDATE operator_sessions SET expires_at_epoch = ?",
                (int(time.time()) - 1,),
            )
            conn.commit()
        finally:
            conn.close()

        denied = client.get(
            "/api/v1/operator/dashboard",
            headers={"X-Operator-Key": token},
        )
        assert denied.status_code == 401


def test_bootstrap_key_remains_temporary_migration_fallback(
    tmp_path,
    monkeypatch,
):
    main, _ = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        response = client.get(
            "/api/v1/operator/dashboard",
            headers={"X-Operator-Key": "bootstrap-secret"},
        )
        assert response.status_code == 200


def test_unsupported_scope_is_rejected(tmp_path, monkeypatch):
    main, _ = load_app(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/operator/auth",
            headers={"X-Operator-Key": "bootstrap-secret"},
            json={"scopes": ["operator:root"]},
        )
        assert response.status_code == 409


def test_production_bootstrap_key_only_issues_scoped_sessions(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "operator-production.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))
    monkeypatch.setenv("INARENA_ENV", "production")
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "bootstrap-secret")
    monkeypatch.setenv("INARENA_ALLOWED_ORIGINS", "https://app.example")
    monkeypatch.delenv("INARENA_DATABASE_URL", raising=False)
    monkeypatch.delenv("INARENA_ENABLE_LEGACY_API", raising=False)

    import app.db as db
    import app.main as main

    importlib.reload(db)
    importlib.reload(main)

    with TestClient(main.app) as client:
        direct = client.get(
            "/api/v1/operator/dashboard",
            headers={"X-Operator-Key": "bootstrap-secret"},
        )
        assert direct.status_code == 401

        auth = client.post(
            "/api/v1/operator/auth",
            headers={"X-Operator-Key": "bootstrap-secret"},
            json={"scopes": ["operator:read"]},
        )
        assert auth.status_code == 200
        token = auth.json()["token"]

        scoped = client.get(
            "/api/v1/operator/dashboard",
            headers={"X-Operator-Key": token},
        )
        assert scoped.status_code == 200


def test_table_creation_requires_operator_write_scope(tmp_path, monkeypatch):
    main, _ = load_app(tmp_path, monkeypatch)
    with TestClient(main.app) as client:
        auth = client.post("/api/v1/operator/auth", headers={"X-Operator-Key": "bootstrap-secret"}, json={"scopes": ["operator:read"]})
        read_token = auth.json()["token"]
        for headers in ({}, {"X-Operator-Key": "invalid"}, {"X-Operator-Key": read_token}):
            denied = client.post("/api/v1/operator/tables", headers=headers, json={"name": "Forbidden table"})
            assert denied.status_code == 401
        assert client.get("/api/v1/tables").json() == []
        auth = client.post("/api/v1/operator/auth", headers={"X-Operator-Key": "bootstrap-secret"}, json={"scopes": []})
        created = client.post("/api/v1/operator/tables", headers={"X-Operator-Key": auth.json()["token"]}, json={"name": "Owner table"})
        assert created.status_code == 201
        assert created.json()["name"] == "Owner table"


def test_remembered_session_lasts_30_days_and_can_be_revoked(tmp_path, monkeypatch):
    main, _ = load_app(tmp_path, monkeypatch)
    now = int(time.time())
    with TestClient(main.app) as client:
        auth = client.post('/api/v1/operator/auth',
            headers={'X-Operator-Key': 'bootstrap-secret'},
            json={'scopes': ['operator:read'], 'remember_me': True})
        assert auth.status_code == 200
        session = auth.json()
        assert now + 30 * 86400 <= session['expires_at_epoch'] <= int(time.time()) + 30 * 86400
        headers = {'X-Operator-Key': session['token']}
        monkeypatch.setattr('app.service.time.time', lambda: now + 7200)
        assert client.get('/api/v1/operator/dashboard', headers=headers).status_code == 200
        assert client.post('/api/v1/operator/balance', headers=headers,
                           json={'user_id': 'p1', 'delta': 100}).status_code == 401
        assert client.post('/api/v1/operator/auth/revoke', headers=headers).status_code == 204
        assert client.get('/api/v1/operator/dashboard', headers=headers).status_code == 401


def test_unremembered_session_retains_configured_ttl(tmp_path, monkeypatch):
    main, _ = load_app(tmp_path, monkeypatch)
    monkeypatch.setenv('INARENA_OPERATOR_SESSION_TTL_SECONDS', '600')
    now = int(time.time())
    with TestClient(main.app) as client:
        auth = client.post('/api/v1/operator/auth',
            headers={'X-Operator-Key': 'bootstrap-secret'}, json={'scopes': []})
        assert auth.status_code == 200
        assert now + 600 <= auth.json()['expires_at_epoch'] <= int(time.time()) + 600
