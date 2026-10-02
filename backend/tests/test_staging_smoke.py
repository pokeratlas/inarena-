from __future__ import annotations

import importlib
import os
import uuid

import pytest
from fastapi.testclient import TestClient


POSTGRES_URL = os.getenv("INARENA_TEST_POSTGRES_URL")
REDIS_URL = os.getenv("INARENA_TEST_REDIS_URL")


@pytest.mark.skipif(
    not POSTGRES_URL or not REDIS_URL,
    reason="staging smoke requires PostgreSQL and Redis",
)
def test_staging_smoke_ready_auth_table_and_realtime(monkeypatch):
    monkeypatch.setenv("INARENA_DATABASE_URL", POSTGRES_URL)
    monkeypatch.setenv("INARENA_REDIS_URL", REDIS_URL)
    monkeypatch.setenv("INARENA_ENV", "staging")
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.delenv("INARENA_ENABLE_LEGACY_API", raising=False)
    monkeypatch.delenv("INARENA_DB_PATH", raising=False)

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    suffix = uuid.uuid4().hex[:8]

    with TestClient(main.app) as client:
        ready = client.get("/ready")
        assert ready.status_code == 200
        ready_body = ready.json()
        assert ready_body["status"] == "ready"
        assert ready_body["checks"]["database_backend"] == "postgresql"
        assert ready_body["checks"]["realtime_coordination"]["configured"] is True
        assert ready_body["checks"]["realtime_coordination"]["connected"] is True

        created = client.post(
            "/api/v1/operator/tables",
            headers={"X-Operator-Key": "operator"},
            json={"name": f"Staging Smoke {suffix}"},
        )
        assert created.status_code == 201
        table_id = created.json()["id"]

        configured = client.post(
            f"/api/v1/operator/tables/{table_id}/configure",
            headers={"X-Operator-Key": "operator"},
            json={
                "table_mode": "cash",
                "starting_stack": 1000,
                "small_blind": 50,
                "big_blind": 100,
                "blind_schedule": [],
                "cash_buyin_min": 500,
                "cash_buyin_max": 5000,
            },
        )
        assert configured.status_code == 200

        sessions = []
        for player in ("p1", "p2"):
            user_id = f"{player}-{suffix}"
            session = service.create_session(user_id, "smoke", {})
            sessions.append(session)
            credited = client.post(
                "/api/v1/operator/balance",
                headers={"X-Operator-Key": "operator"},
                json={"user_id": user_id, "delta": 2000},
            )
            assert credited.status_code == 200

        current = client.get(
            "/api/v1/auth/session",
            headers={"X-Session-ID": sessions[0]["session_id"]},
        )
        assert current.status_code == 200
        assert current.json()["user_id"] == sessions[0]["user_id"]

        for seat_no, session in enumerate(sessions, start=1):
            joined = client.post(
                f"/api/v1/tables/{table_id}/join-auth",
                headers={
                    "X-Session-ID": session["session_id"],
                    "Idempotency-Key": f"smoke-join-{seat_no}-{suffix}",
                },
                json={"seat_no": seat_no, "stack": 1000},
            )
            assert joined.status_code == 200

        with client.websocket_connect(f"/ws/tables/{table_id}") as socket:
            snapshot = socket.receive_json()
            assert snapshot["type"] == "table_snapshot"
            assert snapshot["data"]["id"] == table_id

            started = client.post(
                f"/api/v1/operator/tables/{table_id}/start-hand",
                headers={"X-Operator-Key": "operator"},
                json={"button_seat": 1},
            )
            assert started.status_code == 200

            hand_event = socket.receive_json()
            assert hand_event["type"] == "table_event"
            assert hand_event["event_type"] == "hand_started"
            assert hand_event["data"]["active_hand"] is not None

            folded = client.post(
                f"/api/v1/tables/{table_id}/action-auth",
                headers={
                    "X-Session-ID": sessions[0]["session_id"],
                    "Idempotency-Key": f"smoke-fold-{suffix}",
                },
                json={"action": "fold", "expected_action_no": 0},
            )
            assert folded.status_code == 200
            assert folded.json()["active_hand"] is None

            completed = socket.receive_json()
            assert completed["type"] == "table_event"
            assert completed["event_type"] == "hand_completed"
            assert completed["data"]["active_hand"] is None
