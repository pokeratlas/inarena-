from __future__ import annotations

import importlib
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "finish-balance.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as client:
        yield client, db_path, service


def make_table(client: TestClient, name: str = "Policy") -> str:
    return client.post("/api/v1/tables", json={"name": name}).json()["id"]


def make_session(client: TestClient, user_id: str) -> str:
    response = client.post(
        "/api/v1/sessions",
        json={"user_id": user_id, "provider": "test", "data": {}},
    )
    assert response.status_code == 201
    return response.json()["session_id"]


def configure_tournament(client: TestClient, table_id: str):
    return client.post(
        f"/api/v1/operator/tables/{table_id}/configure",
        headers={"X-Operator-Key": "operator"},
        json={
            "table_mode": "tournament",
            "starting_stack": 1000,
            "small_blind": 50,
            "big_blind": 100,
            "blind_schedule": [
                {"small_blind": 50, "big_blind": 100, "duration_seconds": 60}
            ],
            "cash_buyin_min": 1000,
            "cash_buyin_max": 5000,
            "rebuy_enabled": True,
            "rebuy_stack": 1000,
            "rebuy_max_per_player": 1,
            "addon_enabled": True,
            "addon_stack": 500,
        },
    )


def test_addon_is_one_time_and_window_controlled(env):
    client, _, _ = env
    table_id = make_table(client)
    assert configure_tournament(client, table_id).status_code == 200

    sid = make_session(client, "p1")
    joined = client.post(
        f"/api/v1/tables/{table_id}/join-auth",
        headers={"X-Session-ID": sid},
        json={"seat_no": 1, "stack": 1},
    )
    assert joined.status_code == 200

    first = client.post(
        f"/api/v1/tables/{table_id}/addon",
        headers={"X-Session-ID": sid},
    )
    assert first.status_code == 200
    seat = first.json()["seats"][0]
    assert seat["addon_used"] == 1
    assert seat["stack"] == 1500

    second = client.post(
        f"/api/v1/tables/{table_id}/addon",
        headers={"X-Session-ID": sid},
    )
    assert second.status_code == 409

    closed = client.post(
        f"/api/v1/operator/tables/{table_id}/window/addon",
        headers={"X-Operator-Key": "operator"},
        json={"open": False},
    )
    assert closed.status_code == 200
    assert closed.json()["addon_window_open"] is False


def test_tournament_finish_place_and_winner_after_rebuy_window_closes(env):
    client, db_path, service = env
    table_id = make_table(client)
    assert configure_tournament(client, table_id).status_code == 200

    for player_id, seat_no in (("p1", 1), ("p2", 2)):
        sid = make_session(client, player_id)
        assert client.post(
            f"/api/v1/tables/{table_id}/join-auth",
            headers={"X-Session-ID": sid},
            json={"seat_no": seat_no, "stack": 1},
        ).status_code == 200

    assert client.post(
        f"/api/v1/operator/tables/{table_id}/window/rebuy",
        headers={"X-Operator-Key": "operator"},
        json={"open": False},
    ).status_code == 200

    started = client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    )
    assert started.status_code == 200

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE runtime_seats SET stack = 0 WHERE table_id = ? AND player_id = 'p1'",
            (table_id,),
        )
        conn.execute(
            "UPDATE active_hands SET pot = 150 WHERE table_id = ?",
            (table_id,),
        )
        conn.commit()
    finally:
        conn.close()

    state = service.complete_hand(table_id, {"p1": 0, "p2": 150})
    seats = {seat["player_id"]: seat for seat in state["seats"]}
    assert seats["p1"]["status"] == "eliminated"
    assert seats["p1"]["finish_place"] == 2
    assert seats["p2"]["finish_place"] == 1
    assert state["winner_player_id"] == "p2"
    assert state["finished_at"] is not None


def test_production_cash_balance_buyin_and_cashout(tmp_path, monkeypatch):
    db_path = tmp_path / "balance-prod.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.delenv("INARENA_ENABLE_LEGACY_API", raising=False)

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as client:
        created = client.post(
            "/api/v1/operator/tables",
            headers={"X-Operator-Key": "operator"},
            json={"name": "Cash"},
        )
        assert created.status_code == 201
        table_id = created.json()["id"]

        configured = client.post(
            f"/api/v1/operator/tables/{table_id}/configure",
            headers={"X-Operator-Key": "operator"},
            json={
                "table_mode": "cash",
                "starting_stack": 2000,
                "small_blind": 50,
                "big_blind": 100,
                "blind_schedule": [],
                "cash_buyin_min": 1000,
                "cash_buyin_max": 5000,
            },
        )
        assert configured.status_code == 200

        session = service.create_session("cash-player", "test", {})
        sid = session["session_id"]

        credited = client.post(
            "/api/v1/operator/balance",
            headers={"X-Operator-Key": "operator"},
            json={"user_id": "cash-player", "delta": 4000},
        )
        assert credited.status_code == 200
        assert credited.json()["balance"] == 4000

        joined = client.post(
            f"/api/v1/tables/{table_id}/join-auth",
            headers={"X-Session-ID": sid},
            json={"seat_no": 1, "stack": 2000},
        )
        assert joined.status_code == 200

        balance = client.get(
            "/api/v1/me/balance",
            headers={"X-Session-ID": sid},
        )
        assert balance.status_code == 200
        assert balance.json()["balance"] == 2000

        left = client.post(
            f"/api/v1/tables/{table_id}/stand-auth",
            headers={"X-Session-ID": sid},
        )
        assert left.status_code == 200

        balance = client.get(
            "/api/v1/me/balance",
            headers={"X-Session-ID": sid},
        )
        assert balance.json()["balance"] == 4000


def test_table_close_blocks_new_players_and_is_audited(env):
    client, _, _ = env
    table_id = make_table(client)
    headers = {"X-Operator-Key": "operator"}

    closed = client.post(
        f"/api/v1/operator/tables/{table_id}/close",
        headers=headers,
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    sid = make_session(client, "late-player")
    blocked = client.post(
        f"/api/v1/tables/{table_id}/join-auth",
        headers={"X-Session-ID": sid},
        json={"seat_no": 1, "stack": 1000},
    )
    assert blocked.status_code == 409

    audit = client.get(
        "/api/v1/operator/audit",
        headers=headers,
        params={"table_id": table_id},
    )
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.json()]
    assert "table_closed" in actions
