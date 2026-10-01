from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.poker import evaluate_seven


def test_evaluator_orders_straight_flush_above_quads():
    straight_flush = evaluate_seven(
        ["Ah", "Kh", "Qh", "Jh", "Th", "2c", "3d"]
    )
    quads = evaluate_seven(
        ["As", "Ah", "Ad", "Ac", "Kd", "2c", "3d"]
    )
    assert straight_flush > quads


def test_evaluator_supports_wheel_straight():
    wheel = evaluate_seven(
        ["Ah", "2c", "3d", "4s", "5h", "Kd", "Qc"]
    )
    assert wheel[0] == 4
    assert wheel[1] == 5


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "showdown.sqlite3"))
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as test_client:
        yield test_client


def test_full_hand_reaches_and_settles_showdown(client):
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Showdown"},
    ).json()["id"]

    for player_id, seat_no in (("p1", 1), ("p2", 2)):
        joined = client.post(
            f"/api/v1/tables/{table_id}/join",
            json={
                "player_id": player_id,
                "seat_no": seat_no,
                "stack": 1000,
            },
        )
        assert joined.status_code == 200

    assert client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    ).status_code == 200

    sequence = [
        ("p1", "call"),
        ("p2", "check"),
        ("p2", "check"),
        ("p1", "check"),
        ("p2", "check"),
        ("p1", "check"),
        ("p2", "check"),
        ("p1", "check"),
    ]
    for action_no, (player_id, action) in enumerate(sequence):
        response = client.post(
            f"/api/v1/tables/{table_id}/action",
            json={
                "player_id": player_id,
                "action": action,
                "expected_action_no": action_no,
            },
        )
        assert response.status_code == 200

    state = client.get(f"/api/v1/tables/{table_id}").json()
    assert state["active_hand"]["state"]["showdown_pending"] is True
    assert len(state["active_hand"]["state"]["board"]) == 5

    settled = client.post(
        f"/api/v1/operator/tables/{table_id}/settle-showdown",
        headers={"X-Operator-Key": "operator"},
    )
    assert settled.status_code == 200
    assert settled.json()["active_hand"] is None
    assert settled.json()["status"] == "open"
