from __future__ import annotations

import importlib
import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def dry_run(tmp_path, monkeypatch):
    db_path = tmp_path / "internal-dry-run.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")
    monkeypatch.setenv("INARENA_ENV", "test")

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as client:
        yield client, db_path


def _play_passive_to_showdown(
    client: TestClient,
    table_id: str,
    state: dict,
    *,
    max_actions: int = 100,
) -> dict:
    for _ in range(max_actions):
        hand = state.get("active_hand")
        if hand is None:
            return state

        action_seat = hand["action_seat"]
        assert action_seat is not None
        actor = next(
            seat["player_id"]
            for seat in state["seats"]
            if seat["seat_no"] == action_seat
        )

        hand_state = hand["state"]
        current_bet = int(hand_state.get("current_bet", 0))
        player_street = int(
            hand_state.get("street_contributions", {}).get(actor, 0)
        )
        action = "call" if current_bet > player_street else "check"

        response = client.post(
            f"/api/v1/tables/{table_id}/action",
            json={
                "player_id": actor,
                "action": action,
                "expected_action_no": int(hand_state["action_no"]),
            },
        )
        assert response.status_code == 200, response.text
        state = response.json()

    raise AssertionError("dry run exceeded maximum action count")


def test_internal_cash_dry_run_six_players_to_showdown(dry_run):
    client, _ = dry_run
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Internal Cash Dry Run"},
    ).json()["id"]

    starting_stack = 5_000
    players = [f"cash-p{index}" for index in range(1, 7)]
    for seat_no, player_id in enumerate(players, start=1):
        joined = client.post(
            f"/api/v1/tables/{table_id}/join",
            json={
                "player_id": player_id,
                "seat_no": seat_no,
                "stack": starting_stack,
            },
        )
        assert joined.status_code == 200

    initial_total = starting_stack * len(players)
    started = client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    )
    assert started.status_code == 200

    final_state = _play_passive_to_showdown(
        client,
        table_id,
        started.json(),
    )

    assert final_state["active_hand"] is None
    assert final_state["status"] == "open"
    assert sum(seat["stack"] for seat in final_state["seats"]) == initial_total

    history = client.get(f"/api/v1/tables/{table_id}/hands").json()
    assert len(history) == 1
    assert history[0]["pot"] == 600
    assert sum(history[0]["payouts"].values()) == history[0]["pot"]

    actions = client.get(
        f"/api/v1/tables/{table_id}/hands/{history[0]['hand_id']}/actions"
    ).json()
    assert len(actions) >= 6
    assert {item["action"] for item in actions}.issubset({"call", "check"})


def test_internal_tournament_dry_run_registration_to_winner(dry_run):
    client, db_path = dry_run
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Internal Tournament Dry Run"},
    ).json()["id"]

    headers = {"X-Operator-Key": "operator"}
    configured = client.post(
        f"/api/v1/operator/tables/{table_id}/configure",
        headers=headers,
        json={
            "table_mode": "tournament",
            "starting_stack": 100,
            "small_blind": 50,
            "big_blind": 100,
            "blind_schedule": [
                {
                    "small_blind": 50,
                    "big_blind": 100,
                    "duration_seconds": 600,
                }
            ],
            "cash_buyin_min": 1000,
            "cash_buyin_max": 10000,
            "rebuy_enabled": False,
            "rebuy_stack": 0,
            "rebuy_max_per_player": 0,
            "addon_enabled": False,
            "addon_stack": 0,
        },
    )
    assert configured.status_code == 200

    now = int(time.time())
    lifecycle = client.post(
        f"/api/v1/operator/tables/{table_id}/tournament/lifecycle",
        headers=headers,
        json={
            "registration_open_at": now - 60,
            "registration_close_at": now + 60,
            "scheduled_start_at": now + 120,
            "late_registration_close_at": now + 600,
        },
    )
    assert lifecycle.status_code == 200

    opened = client.post(
        f"/api/v1/operator/tables/{table_id}/tournament/open-registration",
        headers=headers,
    )
    assert opened.status_code == 200

    sessions: dict[str, str] = {}
    for seat_no, player_id in enumerate(
        ("t-p1", "t-p2", "t-p3", "t-p4"),
        start=1,
    ):
        session = client.post(
            "/api/v1/sessions",
            json={
                "user_id": player_id,
                "provider": "test",
                "data": {},
            },
        ).json()["session_id"]
        sessions[player_id] = session

        registered = client.post(
            f"/api/v1/tournaments/{table_id}/register",
            headers={"X-Session-ID": session},
        )
        assert registered.status_code == 200

        seated = client.post(
            f"/api/v1/tables/{table_id}/join-auth",
            headers={"X-Session-ID": session},
            json={"seat_no": seat_no, "stack": 1},
        )
        assert seated.status_code == 200
        assert next(
            seat for seat in seated.json()["seats"]
            if seat["player_id"] == player_id
        )["stack"] == 100

    rebuy_closed = client.post(
        f"/api/v1/operator/tables/{table_id}/window/rebuy",
        headers=headers,
        json={"open": False},
    )
    assert rebuy_closed.status_code == 200

    running = client.post(
        f"/api/v1/operator/tables/{table_id}/tournament/start",
        headers=headers,
    )
    assert running.status_code == 200
    assert running.json()["tournament_status"] == "running"

    started = client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    )
    assert started.status_code == 200
    state = started.json()
    hand_id = state["active_hand"]["hand_id"]

    # Deterministic internal dry run: t-p1 has the winning hand and the
    # remaining deck produces a neutral board.
    conn = sqlite3.connect(db_path)
    try:
        cards = {
            "t-p1": ["Ah", "Ad"],
            "t-p2": ["Kh", "Kd"],
            "t-p3": ["Qh", "Qd"],
            "t-p4": ["Jh", "Jd"],
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

        # _draw_from_deck pops from the end.
        deterministic_deck = ["9h", "5c", "4s", "3d", "2c"]
        conn.execute(
            """
            UPDATE hand_secrets
            SET deck_json = ?
            WHERE hand_id = ?
            """,
            (json.dumps(deterministic_deck), hand_id),
        )
        conn.commit()
    finally:
        conn.close()

    final_state = _play_passive_to_showdown(
        client,
        table_id,
        state,
        max_actions=20,
    )

    assert final_state["active_hand"] is None
    assert final_state["tournament_status"] == "finished"
    assert final_state["winner_player_id"] == "t-p1"
    assert final_state["finished_at"] is not None

    places = {
        seat["player_id"]: seat["finish_place"]
        for seat in final_state["seats"]
    }
    assert places["t-p1"] == 1
    assert set(places.values()) == {1, 2, 3, 4}
    assert sum(seat["stack"] for seat in final_state["seats"]) == 400

    results = client.get(
        f"/api/v1/operator/reports/tournaments/{table_id}/results",
        headers=headers,
    )
    assert results.status_code == 200
    result_rows = results.json()
    assert len(result_rows) == 4
    assert next(row for row in result_rows if row["player_id"] == "t-p1")[
        "winner"
    ] is True
