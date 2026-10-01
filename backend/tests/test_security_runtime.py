from __future__ import annotations

import importlib
import time

from fastapi.testclient import TestClient


def _reload_app():
    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)
    return main


def test_legacy_join_and_action_are_hidden_outside_test_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "prod.sqlite3"))
    monkeypatch.delenv("INARENA_ENABLE_LEGACY_API", raising=False)

    main = _reload_app()
    with TestClient(main.app) as client:
        table_id = client.post(
            "/api/v1/tables",
            json={"name": "Prod"},
        ).json()["id"]

        legacy_join = client.post(
            f"/api/v1/tables/{table_id}/join",
            json={
                "player_id": "spoofed",
                "seat_no": 1,
                "stack": 1000,
            },
        )
        assert legacy_join.status_code == 404

        legacy_session = client.post(
            "/api/v1/sessions",
            json={
                "user_id": "spoofed",
                "provider": "test",
                "data": {},
            },
        )
        assert legacy_session.status_code == 404


def test_operator_can_change_blinds_only_between_hands(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "blinds.sqlite3"))
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")

    main = _reload_app()
    with TestClient(main.app) as client:
        table_id = client.post(
            "/api/v1/tables",
            json={"name": "Blinds"},
        ).json()["id"]
        headers = {"X-Operator-Key": "operator"}

        changed = client.post(
            f"/api/v1/operator/tables/{table_id}/blinds",
            headers=headers,
            json={"small_blind": 100, "big_blind": 200},
        )
        assert changed.status_code == 200

        for player_id, seat_no in (("p1", 1), ("p2", 2)):
            assert client.post(
                f"/api/v1/tables/{table_id}/join",
                json={
                    "player_id": player_id,
                    "seat_no": seat_no,
                    "stack": 2000,
                },
            ).status_code == 200

        started = client.post(
            f"/api/v1/tables/{table_id}/start-hand",
            json={"button_seat": 1},
        )
        assert started.status_code == 200
        hand = started.json()["active_hand"]
        assert hand["pot"] == 300
        assert hand["state"]["small_blind"] == 100
        assert hand["state"]["big_blind"] == 200

        blocked = client.post(
            f"/api/v1/operator/tables/{table_id}/blinds",
            headers=headers,
            json={"small_blind": 200, "big_blind": 400},
        )
        assert blocked.status_code == 409


def test_action_deadline_is_persisted_and_moves_with_turn(tmp_path, monkeypatch):
    monkeypatch.setenv("INARENA_DB_PATH", str(tmp_path / "timer.sqlite3"))
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")
    monkeypatch.setenv("INARENA_ACTION_TIMEOUT_SECONDS", "20")

    main = _reload_app()
    with TestClient(main.app) as client:
        table_id = client.post(
            "/api/v1/tables",
            json={"name": "Timer"},
        ).json()["id"]
        for player_id, seat_no in (("p1", 1), ("p2", 2)):
            client.post(
                f"/api/v1/tables/{table_id}/join",
                json={
                    "player_id": player_id,
                    "seat_no": seat_no,
                    "stack": 1000,
                },
            )

        started = client.post(
            f"/api/v1/tables/{table_id}/start-hand",
            json={"button_seat": 1},
        ).json()
        state = started["active_hand"]["state"]
        first_deadline = state["action_deadline_epoch"]
        assert state["action_timeout_seconds"] == 20
        assert first_deadline >= int(time.time()) + 18

        acted = client.post(
            f"/api/v1/tables/{table_id}/action",
            json={
                "player_id": "p1",
                "action": "call",
                "expected_action_no": 0,
            },
        )
        assert acted.status_code == 200
        next_state = acted.json()["active_hand"]["state"]
        assert next_state["action_deadline_epoch"] >= first_deadline - 1
        assert next_state["action_deadline_epoch"] >= int(time.time()) + 18
