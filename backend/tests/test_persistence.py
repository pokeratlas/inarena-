from __future__ import annotations

import importlib
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "inarena-test.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "test-operator-key")

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as test_client:
        yield test_client, db_path


def create_started_table(client: TestClient) -> str:
    table = client.post("/api/v1/tables", json={"name": "Cloud Table"}).json()
    table_id = table["id"]

    r1 = client.post(
        f"/api/v1/tables/{table_id}/join",
        json={"player_id": "p1", "seat_no": 1, "stack": 10000},
    )
    assert r1.status_code == 200

    r2 = client.post(
        f"/api/v1/tables/{table_id}/join",
        json={"player_id": "p2", "seat_no": 2, "stack": 10000},
    )
    assert r2.status_code == 200

    started = client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    )
    assert started.status_code == 200
    return table_id


def test_active_hand_survives_app_restart(client):
    test_client, db_path = client
    table_id = create_started_table(test_client)

    before = test_client.get(f"/api/v1/tables/{table_id}").json()
    hand_id = before["active_hand"]["hand_id"]
    assert before["status"] == "playing"

    import app.db as db
    import app.service as service
    import app.main as main

    os.environ["INARENA_DB_PATH"] = str(db_path)
    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as restarted:
        after = restarted.get(f"/api/v1/tables/{table_id}")
        assert after.status_code == 200
        state = after.json()
        assert state["active_hand"]["hand_id"] == hand_id
        assert [seat["player_id"] for seat in state["seats"]] == ["p1", "p2"]


def test_atomic_hand_completion_updates_stacks_and_audit(client):
    test_client, db_path = client
    table_id = create_started_table(test_client)

    pot_response = test_client.post(
        f"/api/v1/tables/{table_id}/pot",
        json={"pot": 600},
    )
    assert pot_response.status_code == 200
    assert pot_response.json()["active_hand"]["pot"] == 600

    response = test_client.post(
        f"/api/v1/tables/{table_id}/complete-hand",
        json={"payouts": {"p1": 600, "p2": 0}},
    )
    assert response.status_code == 200
    state = response.json()
    assert state["active_hand"] is None
    assert state["status"] == "open"

    stacks = {seat["player_id"]: seat["stack"] for seat in state["seats"]}
    assert stacks == {"p1": 10600, "p2": 10000}

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT pot, payouts_json, stacks_json FROM hand_results"
        ).fetchone()
        assert row is not None
        assert row[0] == 600
        assert '"p1":600' in row[1]
        assert '"p1":10600' in row[2]
    finally:
        conn.close()


def test_invalid_settlement_rolls_back(client):
    test_client, db_path = client
    table_id = create_started_table(test_client)
    test_client.post(f"/api/v1/tables/{table_id}/pot", json={"pot": 500})

    before = test_client.get(f"/api/v1/tables/{table_id}").json()
    response = test_client.post(
        f"/api/v1/tables/{table_id}/complete-hand",
        json={"payouts": {"p1": 400}},
    )
    assert response.status_code == 409

    after = test_client.get(f"/api/v1/tables/{table_id}").json()
    assert after["active_hand"] is not None
    assert after["active_hand"]["hand_id"] == before["active_hand"]["hand_id"]
    assert {s["player_id"]: s["stack"] for s in after["seats"]} == {
        "p1": 10000,
        "p2": 10000,
    }

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM hand_results").fetchone()[0] == 0
    finally:
        conn.close()


def test_duplicate_seat_is_rejected(client):
    test_client, _ = client
    table = test_client.post("/api/v1/tables", json={"name": "T"}).json()
    table_id = table["id"]

    first = test_client.post(
        f"/api/v1/tables/{table_id}/join",
        json={"player_id": "p1", "seat_no": 1, "stack": 1000},
    )
    second = test_client.post(
        f"/api/v1/tables/{table_id}/join",
        json={"player_id": "p2", "seat_no": 1, "stack": 1000},
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_cannot_stand_during_active_hand(client):
    test_client, _ = client
    table_id = create_started_table(test_client)

    response = test_client.post(
        f"/api/v1/tables/{table_id}/stand",
        json={"player_id": "p1"},
    )
    assert response.status_code == 409


def test_session_survives_restart(client):
    test_client, db_path = client
    created = test_client.post(
        "/api/v1/sessions",
        json={
            "user_id": "tg:12345",
            "provider": "telegram",
            "data": {"username": "vipplayer", "chat_id": 12345},
            "expires_at": "2026-12-01T00:00:00Z",
        },
    )
    assert created.status_code == 201
    session = created.json()

    import app.db as db
    import app.service as service
    import app.main as main

    os.environ["INARENA_DB_PATH"] = str(db_path)
    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as restarted:
        response = restarted.get(f"/api/v1/sessions/{session['session_id']}")
        assert response.status_code == 200
        restored = response.json()
        assert restored["provider"] == "telegram"
        assert restored["user_id"] == "tg:12345"
        assert restored["data"]["chat_id"] == 12345


def test_session_delete_is_persisted(client):
    test_client, _ = client
    created = test_client.post(
        "/api/v1/sessions",
        json={"user_id": "u1", "provider": "email", "data": {}},
    ).json()

    deleted = test_client.delete(f"/api/v1/sessions/{created['session_id']}")
    assert deleted.status_code == 204
    missing = test_client.get(f"/api/v1/sessions/{created['session_id']}")
    assert missing.status_code == 404


def test_websocket_reconnect_receives_persisted_snapshot(client):
    test_client, _ = client
    table_id = create_started_table(test_client)

    with test_client.websocket_connect(f"/ws/tables/{table_id}") as socket:
        message = socket.receive_json()
        assert message["type"] == "table_snapshot"
        assert isinstance(message["seq"], int)
        assert message["data"]["active_hand"] is not None
        assert len(message["data"]["seats"]) == 2


def test_operator_endpoints_require_key(client):
    test_client, _ = client
    unauthorized = test_client.get("/api/v1/operator/tables")
    assert unauthorized.status_code == 401

    authorized = test_client.get(
        "/api/v1/operator/tables",
        headers={"X-Operator-Key": "test-operator-key"},
    )
    assert authorized.status_code == 200


def test_operator_can_pause_and_resume_active_table(client):
    test_client, _ = client
    table_id = create_started_table(test_client)
    headers = {"X-Operator-Key": "test-operator-key"}

    paused = test_client.post(
        f"/api/v1/operator/tables/{table_id}/pause",
        headers=headers,
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["active_hand"] is not None

    resumed = test_client.post(
        f"/api/v1/operator/tables/{table_id}/resume",
        headers=headers,
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "playing"
    assert resumed.json()["active_hand"] is not None


def test_schema_migrations_reach_expected_version(client):
    test_client, db_path = client
    assert test_client.get("/health").status_code == 200

    conn = sqlite3.connect(db_path)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 5
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "realtime_events" in tables
    finally:
        conn.close()


def test_realtime_events_are_monotonic_and_replayable(client):
    test_client, _ = client
    table = test_client.post("/api/v1/tables", json={"name": "Replay"}).json()
    table_id = table["id"]

    first = test_client.post(
        f"/api/v1/tables/{table_id}/join",
        json={"player_id": "p1", "seat_no": 1, "stack": 1000},
    )
    assert first.status_code == 200

    events = test_client.get(
        f"/api/v1/tables/{table_id}/events",
        params={"after_seq": 0},
    )
    assert events.status_code == 200
    data = events.json()
    assert len(data) >= 1
    seqs = [event["seq"] for event in data]
    assert seqs == sorted(seqs)
    assert data[-1]["event_type"] == "player_joined"

    after = seqs[-1]
    second = test_client.post(
        f"/api/v1/tables/{table_id}/stand",
        json={"player_id": "p1"},
    )
    assert second.status_code == 200

    replay = test_client.get(
        f"/api/v1/tables/{table_id}/events",
        params={"after_seq": after},
    ).json()
    assert len(replay) == 1
    assert replay[0]["seq"] > after
    assert replay[0]["event_type"] == "player_stood"


def test_websocket_sync_replays_events_after_sequence(client):
    test_client, _ = client
    table = test_client.post("/api/v1/tables", json={"name": "WS Replay"}).json()
    table_id = table["id"]

    with test_client.websocket_connect(f"/ws/tables/{table_id}") as socket:
        snapshot = socket.receive_json()
        assert snapshot["type"] == "table_snapshot"
        base_seq = snapshot["seq"]

        joined = test_client.post(
            f"/api/v1/tables/{table_id}/join",
            json={"player_id": "p1", "seat_no": 1, "stack": 1000},
        )
        assert joined.status_code == 200

        pushed = socket.receive_json()
        assert pushed["type"] == "table_event"
        assert pushed["seq"] > base_seq

        socket.send_json({"type": "sync", "after_seq": base_seq})
        replay = socket.receive_json()
        assert replay["type"] == "table_replay"
        assert replay["events"][0]["seq"] > base_seq


def test_operator_recovery_requires_pause_and_writes_audit(client):
    test_client, db_path = client
    table_id = create_started_table(test_client)
    headers = {"X-Operator-Key": "test-operator-key"}

    blocked = test_client.post(
        f"/api/v1/operator/tables/{table_id}/abort-hand",
        headers=headers,
        json={"reason": "stuck hand"},
    )
    assert blocked.status_code == 409

    paused = test_client.post(
        f"/api/v1/operator/tables/{table_id}/pause",
        headers=headers,
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    recovered = test_client.post(
        f"/api/v1/operator/tables/{table_id}/abort-hand",
        headers=headers,
        json={"reason": "manual recovery after restart mismatch"},
    )
    assert recovered.status_code == 200
    state = recovered.json()
    assert state["active_hand"] is None
    assert state["status"] == "open"

    audit = test_client.get(
        f"/api/v1/operator/tables/{table_id}/recovery-actions",
        headers=headers,
    )
    assert audit.status_code == 200
    actions = audit.json()
    assert len(actions) == 1
    assert actions[0]["action"] == "abort_hand"
    assert actions[0]["reason"] == "manual recovery after restart mismatch"
    assert actions[0]["hand_id"] is not None
    assert "hand_state" in actions[0]["details"]

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT action, reason FROM recovery_actions WHERE table_id = ?",
            (table_id,),
        ).fetchone()
        assert row == ("abort_hand", "manual recovery after restart mismatch")
    finally:
        conn.close()


def test_operator_recovery_emits_realtime_event(client):
    test_client, _ = client
    table_id = create_started_table(test_client)
    headers = {"X-Operator-Key": "test-operator-key"}

    with test_client.websocket_connect(f"/ws/tables/{table_id}") as socket:
        snapshot = socket.receive_json()
        base_seq = snapshot["seq"]

        test_client.post(
            f"/api/v1/operator/tables/{table_id}/pause",
            headers=headers,
        )
        pause_event = socket.receive_json()
        assert pause_event["event_type"] == "table_paused"

        test_client.post(
            f"/api/v1/operator/tables/{table_id}/abort-hand",
            headers=headers,
            json={"reason": "operator recovery test"},
        )
        recovery_event = socket.receive_json()
        assert recovery_event["type"] == "table_event"
        assert recovery_event["event_type"] == "hand_recovered"
        assert recovery_event["seq"] > base_seq
