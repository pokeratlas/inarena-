from __future__ import annotations

import importlib
import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "runtime2.sqlite3"))
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")
    monkeypatch.setenv("INARENA_SESSION_TTL_SECONDS", "600")

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as test_client:
        yield test_client, tmp_path / "runtime2.sqlite3"


def make_table(client: TestClient) -> str:
    return client.post(
        "/api/v1/tables",
        json={"name": "Runtime"},
    ).json()["id"]


def test_timeout_policy_checks_when_legal_and_folds_facing_bet(client):
    test_client, db_path = client
    table_id = make_table(test_client)
    for player_id, seat_no in (("p1", 1), ("p2", 2)):
        test_client.post(
            f"/api/v1/tables/{table_id}/join",
            json={"player_id": player_id, "seat_no": seat_no, "stack": 1000},
        )
    started = test_client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    ).json()

    conn = sqlite3.connect(db_path)
    try:
        state = json.loads(
            conn.execute(
                "SELECT state_json FROM active_hands WHERE table_id = ?",
                (table_id,),
            ).fetchone()[0]
        )
        state["action_deadline_epoch"] = int(time.time()) - 1
        conn.execute(
            "UPDATE active_hands SET state_json = ? WHERE table_id = ?",
            (json.dumps(state, separators=(",", ":")), table_id),
        )
        conn.commit()
    finally:
        conn.close()

    resolved = test_client.post(
        f"/api/v1/operator/tables/{table_id}/resolve-timeout",
        headers={"X-Operator-Key": "operator"},
    )
    assert resolved.status_code == 200
    after = resolved.json()
    assert after["active_hand"] is None
    history = test_client.get(f"/api/v1/tables/{table_id}/hands").json()
    actions = test_client.get(
        f"/api/v1/tables/{table_id}/hands/{history[0]['hand_id']}/actions"
    ).json()
    assert actions[-1]["action"] == "fold"

    # New hand: make BB act with no bet faced, then expire.
    test_client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    )
    call = test_client.post(
        f"/api/v1/tables/{table_id}/action",
        json={"player_id": "p1", "action": "call", "expected_action_no": 0},
    )
    assert call.status_code == 200

    conn = sqlite3.connect(db_path)
    try:
        state = json.loads(
            conn.execute(
                "SELECT state_json FROM active_hands WHERE table_id = ?",
                (table_id,),
            ).fetchone()[0]
        )
        state["action_deadline_epoch"] = int(time.time()) - 1
        conn.execute(
            "UPDATE active_hands SET state_json = ? WHERE table_id = ?",
            (json.dumps(state, separators=(",", ":")), table_id),
        )
        conn.commit()
    finally:
        conn.close()

    checked = test_client.post(
        f"/api/v1/operator/tables/{table_id}/resolve-timeout",
        headers={"X-Operator-Key": "operator"},
    )
    assert checked.status_code == 200
    assert checked.json()["active_hand"]["street"] == "flop"


def test_tournament_schedule_advances_between_hands(client):
    test_client, db_path = client
    table_id = make_table(test_client)
    headers = {"X-Operator-Key": "operator"}

    configured = test_client.post(
        f"/api/v1/operator/tables/{table_id}/configure",
        headers=headers,
        json={
            "table_mode": "tournament",
            "starting_stack": 5000,
            "small_blind": 50,
            "big_blind": 100,
            "blind_schedule": [
                {"small_blind": 50, "big_blind": 100, "duration_seconds": 60},
                {"small_blind": 100, "big_blind": 200, "duration_seconds": 60},
            ],
        },
    )
    assert configured.status_code == 200
    state = configured.json()
    assert state["table_mode"] == "tournament"
    assert state["small_blind"] == 50
    assert state["big_blind"] == 100

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            UPDATE runtime_tables
            SET blind_level_started_at = ?
            WHERE id = ?
            """,
            (int(time.time()) - 61, table_id),
        )
        conn.commit()
    finally:
        conn.close()

    for player_id, seat_no in (("p1", 1), ("p2", 2)):
        test_client.post(
            f"/api/v1/tables/{table_id}/join",
            json={"player_id": player_id, "seat_no": seat_no, "stack": 5000},
        )

    started = test_client.post(
        f"/api/v1/operator/tables/{table_id}/start-hand",
        headers=headers,
        json={"button_seat": 1},
    )
    assert started.status_code == 200
    hand = started.json()["active_hand"]
    assert hand["state"]["small_blind"] == 100
    assert hand["state"]["big_blind"] == 200
    assert hand["state"]["blind_level_index"] == 1


def test_session_expiry_refresh_and_dashboard(client):
    test_client, db_path = client
    session = test_client.post(
        "/api/v1/sessions",
        json={"user_id": "p1", "provider": "test", "data": {}},
    ).json()
    session_id = session["session_id"]

    current = test_client.get(
        "/api/v1/auth/session",
        headers={"X-Session-ID": session_id},
    )
    assert current.status_code == 200

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE auth_sessions SET expires_at = ? WHERE session_id = ?",
            ("2000-01-01T00:00:00Z", session_id),
        )
        conn.commit()
    finally:
        conn.close()

    expired = test_client.get(
        "/api/v1/auth/session",
        headers={"X-Session-ID": session_id},
    )
    assert expired.status_code == 401

    # Create another live session and verify refresh extends it.
    live = test_client.post(
        "/api/v1/sessions",
        json={"user_id": "p2", "provider": "test", "data": {}},
    ).json()
    refreshed = test_client.post(
        "/api/v1/auth/refresh",
        headers={"X-Session-ID": live["session_id"]},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["expires_at"] != live["expires_at"]

    dashboard = test_client.get(
        "/api/v1/operator/dashboard",
        headers={"X-Operator-Key": "operator"},
    )
    assert dashboard.status_code == 200
    data = dashboard.json()
    assert "active_sessions" in data
    assert data["active_sessions"] >= 1
    assert "tables" in data
