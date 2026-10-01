from __future__ import annotations

import importlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "rules.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as client:
        yield client, db_path, service


def make_table(client: TestClient, stacks: dict[str, int]) -> str:
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Rules"},
    ).json()["id"]
    for seat_no, (player_id, stack) in enumerate(stacks.items(), start=1):
        response = client.post(
            f"/api/v1/tables/{table_id}/join",
            json={
                "player_id": player_id,
                "seat_no": seat_no,
                "stack": stack,
            },
        )
        assert response.status_code == 200
    return table_id


def test_heads_up_blinds_and_preflop_order(env):
    client, _, _ = env
    table_id = make_table(client, {"p1": 1000, "p2": 1000})

    state = client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    ).json()
    hand = state["active_hand"]

    assert hand["button_seat"] == 1
    assert hand["state"]["small_blind_seat"] == 1
    assert hand["state"]["big_blind_seat"] == 2
    assert hand["action_seat"] == 1
    assert hand["pot"] == 150
    assert hand["state"]["current_bet"] == 100
    assert hand["state"]["min_raise"] == 100
    assert {s["player_id"]: s["stack"] for s in state["seats"]} == {
        "p1": 950,
        "p2": 900,
    }


def test_dealer_button_rotates_after_completed_hand(env):
    client, _, _ = env
    table_id = make_table(
        client,
        {"p1": 1000, "p2": 1000, "p3": 1000},
    )

    first = client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    ).json()
    assert first["active_hand"]["button_seat"] == 1
    assert first["active_hand"]["action_seat"] == 1

    assert client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": "p1",
            "action": "fold",
            "expected_action_no": 0,
        },
    ).status_code == 200
    finished = client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": "p2",
            "action": "fold",
            "expected_action_no": 1,
        },
    )
    assert finished.status_code == 200
    assert finished.json()["active_hand"] is None

    second = client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={},
    )
    assert second.status_code == 200
    assert second.json()["active_hand"]["button_seat"] == 2


def test_minimum_raise_is_enforced(env):
    client, _, _ = env
    table_id = make_table(
        client,
        {"p1": 1000, "p2": 1000, "p3": 1000},
    )
    client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    )

    too_small = client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": "p1",
            "action": "raise",
            "amount": 150,
            "expected_action_no": 0,
        },
    )
    assert too_small.status_code == 409

    full_raise = client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": "p1",
            "action": "raise",
            "amount": 200,
            "expected_action_no": 0,
        },
    )
    assert full_raise.status_code == 200
    hand = full_raise.json()["active_hand"]
    assert hand["state"]["current_bet"] == 200
    assert hand["state"]["min_raise"] == 100


def test_uncontested_fold_auto_settles_and_creates_history(env):
    client, _, _ = env
    table_id = make_table(client, {"p1": 1000, "p2": 1000})
    client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    )

    folded = client.post(
        f"/api/v1/tables/{table_id}/action",
        json={
            "player_id": "p1",
            "action": "fold",
            "expected_action_no": 0,
        },
    )
    assert folded.status_code == 200
    state = folded.json()
    assert state["active_hand"] is None
    assert state["status"] == "open"
    assert {s["player_id"]: s["stack"] for s in state["seats"]} == {
        "p1": 950,
        "p2": 1050,
    }

    history = client.get(f"/api/v1/tables/{table_id}/hands").json()
    assert len(history) == 1
    assert history[0]["pot"] == 150
    assert history[0]["payouts"]["p2"] == 150

    actions = client.get(
        f"/api/v1/tables/{table_id}/hands/{history[0]['hand_id']}/actions"
    ).json()
    assert len(actions) == 1
    assert actions[0]["action"] == "fold"


def test_side_pots_are_split_by_contribution_tiers(env):
    client, db_path, service = env
    table_id = make_table(
        client,
        {"p1": 1000, "p2": 1000, "p3": 1000},
    )
    started = client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    ).json()
    hand_id = started["active_hand"]["hand_id"]

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT state_json FROM active_hands WHERE table_id = ?",
            (table_id,),
        ).fetchone()
        state = json.loads(row[0])
        state.update(
            {
                "pot": 700,
                "board": ["2c", "3d", "4h", "5s", "9c"],
                "showdown_pending": True,
                "folded": [],
                "contributions": {
                    "p1": 100,
                    "p2": 300,
                    "p3": 300,
                },
                "action_seat": None,
                "street": "river",
            }
        )
        conn.execute(
            """
            UPDATE active_hands
            SET pot = 700, street = 'river', action_seat = NULL,
                state_json = ?
            WHERE table_id = ?
            """,
            (json.dumps(state, separators=(",", ":")), table_id),
        )
        cards = {
            "p1": ["Ah", "Kd"],
            "p2": ["9d", "9h"],
            "p3": ["Ad", "Ac"],
        }
        for player_id, hole in cards.items():
            conn.execute(
                """
                UPDATE hand_private_cards
                SET cards_json = ?
                WHERE hand_id = ? AND player_id = ?
                """,
                (json.dumps(hole), hand_id, player_id),
            )
        conn.commit()
    finally:
        conn.close()

    payouts = service.calculate_showdown_payouts(table_id)
    assert payouts == {"p1": 150, "p2": 0, "p3": 550}
    assert sum(payouts.values()) == 700
