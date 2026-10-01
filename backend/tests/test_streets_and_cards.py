from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "streets.sqlite3"))

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as test_client:
        yield test_client


def create_session(client: TestClient, player_id: str) -> str:
    response = client.post(
        "/api/v1/sessions",
        json={"user_id": player_id, "provider": "test", "data": {}},
    )
    assert response.status_code == 201
    return response.json()["session_id"]


def create_two_player_hand(client: TestClient):
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Street Test"},
    ).json()["id"]

    sessions = {}
    for player_id, seat_no in (("p1", 1), ("p2", 2)):
        session_id = create_session(client, player_id)
        sessions[player_id] = session_id
        joined = client.post(
            f"/api/v1/tables/{table_id}/join-auth",
            headers={"X-Session-ID": session_id},
            json={"seat_no": seat_no, "stack": 1000},
        )
        assert joined.status_code == 200

    started = client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    )
    assert started.status_code == 200
    return table_id, sessions


def act(client, table_id: str, player_id: str, action_no: int):
    response = client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": player_id,
            "action": "check",
            "expected_action_no": action_no,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_private_cards_are_not_exposed_in_public_state(client):
    table_id, sessions = create_two_player_hand(client)

    public = client.get(f"/api/v1/tables/{table_id}")
    assert public.status_code == 200
    public_state = public.json()
    serialized = str(public_state)
    assert "hole_cards" not in serialized
    assert "deck" not in serialized
    assert public_state["active_hand"]["state"]["board"] == []

    p1 = client.get(
        f"/api/v1/tables/{table_id}/view",
        headers={"X-Session-ID": sessions["p1"]},
    ).json()
    p2 = client.get(
        f"/api/v1/tables/{table_id}/view",
        headers={"X-Session-ID": sessions["p2"]},
    ).json()

    assert len(p1["hole_cards"]) == 2
    assert len(p2["hole_cards"]) == 2
    assert set(p1["hole_cards"]).isdisjoint(set(p2["hole_cards"]))


def test_check_rounds_progress_board_to_showdown(client):
    table_id, _ = create_two_player_hand(client)

    response = client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": "p1",
            "action": "call",
            "expected_action_no": 0,
        },
    )
    assert response.status_code == 200
    state = response.json()
    assert state["active_hand"]["street"] == "preflop"

    state = act(client, table_id, "p2", 1)
    assert state["active_hand"]["street"] == "flop"
    assert len(state["active_hand"]["state"]["board"]) == 3

    state = act(client, table_id, "p2", 2)
    state = act(client, table_id, "p1", 3)
    assert state["active_hand"]["street"] == "turn"
    assert len(state["active_hand"]["state"]["board"]) == 4

    state = act(client, table_id, "p2", 4)
    state = act(client, table_id, "p1", 5)
    assert state["active_hand"]["street"] == "river"
    assert len(state["active_hand"]["state"]["board"]) == 5

    state = act(client, table_id, "p2", 6)
    state = act(client, table_id, "p1", 7)
    hand = state["active_hand"]
    assert hand["street"] == "river"
    assert hand["action_seat"] is None
    assert hand["state"]["showdown_pending"] is True
    assert len(set(hand["state"]["board"])) == 5


def test_authenticated_join_uses_session_identity(client):
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Identity"},
    ).json()["id"]
    session_id = create_session(client, "tg:777")

    response = client.post(
        f"/api/v1/tables/{table_id}/join-auth",
        headers={"X-Session-ID": session_id},
        json={"seat_no": 4, "stack": 2500},
    )
    assert response.status_code == 200
    seat = response.json()["seats"][0]
    assert seat["player_id"] == "tg:777"
    assert seat["seat_no"] == 4
