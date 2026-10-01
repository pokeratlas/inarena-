from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "actions.sqlite3"))
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as test_client:
        yield test_client


def started_table(client: TestClient) -> str:
    table_id = client.post("/api/v1/tables", json={"name": "Actions"}).json()["id"]
    for player_id, seat_no in (("p1", 1), ("p2", 2)):
        response = client.post(
            f"/api/v1/tables/{table_id}/join",
            json={
                "player_id": player_id,
                "seat_no": seat_no,
                "stack": 1000,
            },
        )
        assert response.status_code == 200

    response = client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    )
    assert response.status_code == 200
    return table_id


def test_action_sequence_rejects_wrong_turn_and_stale_replay(client):
    table_id = started_table(client)

    wrong_turn = client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": "p1",
            "action": "check",
            "expected_action_no": 0,
        },
    )
    assert wrong_turn.status_code == 409

    accepted = client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": "p2",
            "action": "check",
            "expected_action_no": 0,
        },
    )
    assert accepted.status_code == 200
    state = accepted.json()
    assert state["active_hand"]["state"]["action_no"] == 1
    assert state["active_hand"]["action_seat"] == 1

    stale = client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": "p1",
            "action": "check",
            "expected_action_no": 0,
        },
    )
    assert stale.status_code == 409


def test_bet_and_call_move_chips_atomically(client):
    table_id = started_table(client)

    bet = client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": "p2",
            "action": "bet",
            "amount": 100,
            "expected_action_no": 0,
        },
    )
    assert bet.status_code == 200
    after_bet = bet.json()
    stacks = {s["player_id"]: s["stack"] for s in after_bet["seats"]}
    assert stacks["p2"] == 900
    assert after_bet["active_hand"]["pot"] == 100
    assert after_bet["active_hand"]["state"]["current_bet"] == 100

    call = client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": "p1",
            "action": "call",
            "expected_action_no": 1,
        },
    )
    assert call.status_code == 200
    after_call = call.json()
    stacks = {s["player_id"]: s["stack"] for s in after_call["seats"]}
    assert stacks == {"p1": 900, "p2": 900}
    assert after_call["active_hand"]["pot"] == 200
    assert after_call["active_hand"]["state"]["action_no"] == 2


def test_action_emits_realtime_sequence(client):
    table_id = started_table(client)

    with client.websocket_connect(f"/ws/tables/{table_id}") as socket:
        snapshot = socket.receive_json()
        base_seq = snapshot["seq"]

        response = client.post(
            f"/api/v1/tables/{table_id}/action",
            json={
                "player_id": "p2",
                "action": "fold",
                "expected_action_no": 0,
            },
        )
        assert response.status_code == 200

        event = socket.receive_json()
        assert event["type"] == "table_event"
        assert event["event_type"] == "player_action"
        assert event["seq"] > base_seq
