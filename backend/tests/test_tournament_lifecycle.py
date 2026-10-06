from __future__ import annotations

import importlib
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "tournament-lifecycle.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as test_client:
        yield test_client, db_path


def make_session(client: TestClient, user_id: str) -> str:
    response = client.post(
        "/api/v1/sessions",
        json={"user_id": user_id, "provider": "test", "data": {}},
    )
    assert response.status_code == 201
    return response.json()["session_id"]


def make_tournament(client: TestClient) -> str:
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Lifecycle"},
    ).json()["id"]
    configured = client.post(
        f"/api/v1/operator/tables/{table_id}/configure",
        headers={"X-Operator-Key": "operator"},
        json={
            "table_mode": "tournament",
            "starting_stack": 5000,
            "small_blind": 50,
            "big_blind": 100,
            "blind_schedule": [
                {"small_blind": 50, "big_blind": 100, "duration_seconds": 60}
            ],
            "cash_buyin_min": 1000,
            "cash_buyin_max": 10000,
        },
    )
    assert configured.status_code == 200
    return table_id


def configure_lifecycle(client: TestClient, table_id: str):
    now = int(time.time())
    response = client.post(
        f"/api/v1/operator/tables/{table_id}/tournament/lifecycle",
        headers={"X-Operator-Key": "operator"},
        json={
            "registration_open_at": now - 10,
            "registration_close_at": now + 60,
            "scheduled_start_at": now + 120,
            "late_registration_close_at": now + 600,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_scheduled_registering_running_lifecycle(client):
    test_client, _ = client
    table_id = make_tournament(test_client)
    configured = configure_lifecycle(test_client, table_id)
    assert configured["tournament_status"] == "scheduled"

    premature = test_client.post(
        f"/api/v1/operator/tables/{table_id}/tournament/start",
        headers={"X-Operator-Key": "operator"},
    )
    assert premature.status_code == 409

    opened = test_client.post(
        f"/api/v1/operator/tables/{table_id}/tournament/open-registration",
        headers={"X-Operator-Key": "operator"},
    )
    assert opened.status_code == 200
    assert opened.json()["tournament_status"] == "registering"

    sessions = [make_session(test_client, "p1"), make_session(test_client, "p2")]
    for sid in sessions:
        registered = test_client.post(
            f"/api/v1/tournaments/{table_id}/register",
            headers={"X-Session-ID": sid},
        )
        assert registered.status_code == 200
        assert registered.json()["status"] == "registered"

    started = test_client.post(
        f"/api/v1/operator/tables/{table_id}/tournament/start",
        headers={"X-Operator-Key": "operator"},
    )
    assert started.status_code == 200
    assert started.json()["tournament_status"] == "running"

    cannot_cancel = test_client.post(
        f"/api/v1/operator/tables/{table_id}/tournament/cancel",
        headers={"X-Operator-Key": "operator"},
    )
    assert cannot_cancel.status_code == 409


def test_late_registration_cutoff_is_enforced(client):
    test_client, db_path = client
    table_id = make_tournament(test_client)
    configure_lifecycle(test_client, table_id)

    assert test_client.post(
        f"/api/v1/operator/tables/{table_id}/tournament/open-registration",
        headers={"X-Operator-Key": "operator"},
    ).status_code == 200

    for player in ("p1", "p2"):
        sid = make_session(test_client, player)
        assert test_client.post(
            f"/api/v1/tournaments/{table_id}/register",
            headers={"X-Session-ID": sid},
        ).status_code == 200

    assert test_client.post(
        f"/api/v1/operator/tables/{table_id}/tournament/start",
        headers={"X-Operator-Key": "operator"},
    ).status_code == 200

    late_sid = make_session(test_client, "late-ok")
    late = test_client.post(
        f"/api/v1/tournaments/{table_id}/register",
        headers={"X-Session-ID": late_sid},
    )
    assert late.status_code == 200

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            UPDATE runtime_tables
            SET late_registration_close_at = ?
            WHERE id = ?
            """,
            (int(time.time()) - 1, table_id),
        )
        conn.commit()
    finally:
        conn.close()

    too_late_sid = make_session(test_client, "late-no")
    rejected = test_client.post(
        f"/api/v1/tournaments/{table_id}/register",
        headers={"X-Session-ID": too_late_sid},
    )
    assert rejected.status_code == 409


def test_registration_can_be_withdrawn_before_start(client):
    test_client, _ = client
    table_id = make_tournament(test_client)
    configure_lifecycle(test_client, table_id)
    test_client.post(
        f"/api/v1/operator/tables/{table_id}/tournament/open-registration",
        headers={"X-Operator-Key": "operator"},
    )

    sid = make_session(test_client, "withdraw")
    assert test_client.post(
        f"/api/v1/tournaments/{table_id}/register",
        headers={"X-Session-ID": sid},
    ).status_code == 200

    removed = test_client.delete(
        f"/api/v1/tournaments/{table_id}/register",
        headers={"X-Session-ID": sid},
    )
    assert removed.status_code == 200
    assert removed.json()["status"] == "withdrawn"

    current = test_client.get(
        f"/api/v1/tournaments/{table_id}/registration",
        headers={"X-Session-ID": sid},
    )
    assert current.status_code == 200
    assert current.json()["status"] == "withdrawn"
