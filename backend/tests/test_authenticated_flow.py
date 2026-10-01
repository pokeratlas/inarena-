from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "authflow.sqlite3"))
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as test_client:
        yield test_client


def session(client: TestClient, user_id: str) -> str:
    response = client.post(
        "/api/v1/sessions",
        json={"user_id": user_id, "provider": "test", "data": {}},
    )
    assert response.status_code == 201
    return response.json()["session_id"]


def test_authenticated_action_payload_does_not_require_player_id(client):
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Authenticated"},
    ).json()["id"]

    p1 = session(client, "p1")
    p2 = session(client, "p2")

    for session_id, seat_no in ((p1, 1), (p2, 2)):
        joined = client.post(
            f"/api/v1/tables/{table_id}/join-auth",
            headers={"X-Session-ID": session_id},
            json={"seat_no": seat_no, "stack": 1000},
        )
        assert joined.status_code == 200

    assert client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    ).status_code == 200

    action = client.post(
        f"/api/v1/tables/{table_id}/action-auth",
        headers={"X-Session-ID": p1},
        json={
            "action": "fold",
            "expected_action_no": 0,
        },
    )
    assert action.status_code == 200
    assert action.json()["active_hand"] is None


def test_player_history_returns_only_own_private_cards(client):
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Private History"},
    ).json()["id"]

    p1 = session(client, "p1")
    p2 = session(client, "p2")
    for session_id, seat_no in ((p1, 1), (p2, 2)):
        client.post(
            f"/api/v1/tables/{table_id}/join-auth",
            headers={"X-Session-ID": session_id},
            json={"seat_no": seat_no, "stack": 1000},
        )

    client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    )
    client.post(
        f"/api/v1/tables/{table_id}/action-auth",
        headers={"X-Session-ID": p1},
        json={"action": "fold", "expected_action_no": 0},
    )

    p1_history = client.get(
        "/api/v1/me/hands",
        headers={"X-Session-ID": p1},
    )
    p2_history = client.get(
        "/api/v1/me/hands",
        headers={"X-Session-ID": p2},
    )

    assert p1_history.status_code == 200
    assert p2_history.status_code == 200
    assert len(p1_history.json()) == 1
    assert len(p2_history.json()) == 1

    p1_hand = p1_history.json()[0]
    p2_hand = p2_history.json()[0]
    assert len(p1_hand["hole_cards"]) == 2
    assert len(p2_hand["hole_cards"]) == 2
    assert set(p1_hand["hole_cards"]).isdisjoint(set(p2_hand["hole_cards"]))
    assert "payouts" not in p1_hand
    assert "final_stacks" not in p1_hand
