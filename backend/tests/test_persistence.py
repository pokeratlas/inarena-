from __future__ import annotations

import importlib
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "inarena-test.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))

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


def test_complete_hand_is_persisted(client):
    test_client, _ = client
    table_id = create_started_table(test_client)

    response = test_client.post(f"/api/v1/tables/{table_id}/complete-hand")
    assert response.status_code == 200
    state = response.json()
    assert state["active_hand"] is None
    assert state["status"] == "open"


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


def test_websocket_reconnect_receives_persisted_snapshot(client):
    test_client, _ = client
    table_id = create_started_table(test_client)

    with test_client.websocket_connect(f"/ws/tables/{table_id}") as socket:
        message = socket.receive_json()
        assert message["type"] == "table_state"
        assert message["data"]["active_hand"] is not None
        assert len(message["data"]["seats"]) == 2
