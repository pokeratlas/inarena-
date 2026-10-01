from __future__ import annotations

import importlib
import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "policies.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")

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
                {"small_blind": 50, "big_blind": 100, "duration_seconds": 60},
                {"small_blind": 100, "big_blind": 200, "duration_seconds": 60},
            ],
            "cash_buyin_min": 1000,
            "cash_buyin_max": 10000,
            "rebuy_enabled": True,
            "rebuy_stack": 1000,
            "rebuy_max_per_player": 1,
            "addon_enabled": True,
            "addon_stack": 500,
        },
    )


def session(client: TestClient, user_id: str) -> str:
    return client.post(
        "/api/v1/sessions",
        json={"user_id": user_id, "provider": "test", "data": {}},
    ).json()["session_id"]


def test_cash_buyin_bounds_and_cashout_ledger(env):
    client, db_path, _ = env
    table_id = make_table(client)
    headers = {"X-Operator-Key": "operator"}

    configured = client.post(
        f"/api/v1/operator/tables/{table_id}/configure",
        headers=headers,
        json={
            "table_mode": "cash",
            "starting_stack": 5000,
            "small_blind": 50,
            "big_blind": 100,
            "blind_schedule": [],
            "cash_buyin_min": 2000,
            "cash_buyin_max": 5000,
        },
    )
    assert configured.status_code == 200

    too_small = client.post(
        f"/api/v1/tables/{table_id}/join",
        json={"player_id": "p1", "seat_no": 1, "stack": 1000},
    )
    assert too_small.status_code == 409

    joined = client.post(
        f"/api/v1/tables/{table_id}/join",
        json={"player_id": "p1", "seat_no": 1, "stack": 3000},
    )
    assert joined.status_code == 200

    stood = client.post(
        f"/api/v1/tables/{table_id}/stand",
        json={"player_id": "p1"},
    )
    assert stood.status_code == 200

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT entry_type, amount
            FROM table_ledger
            WHERE table_id = ? AND player_id = 'p1'
            ORDER BY id
            """,
            (table_id,),
        ).fetchall()
        assert rows == [("buyin", 3000), ("cashout", 3000)]
    finally:
        conn.close()


def test_tournament_elimination_rebuy_and_addon(env):
    client, db_path, service = env
    table_id = make_table(client)
    assert configure_tournament(client, table_id).status_code == 200

    p1_session = session(client, "p1")
    p2_session = session(client, "p2")
    for sid, seat in ((p1_session, 1), (p2_session, 2)):
        assert client.post(
            f"/api/v1/tables/{table_id}/join-auth",
            headers={"X-Session-ID": sid},
            json={"seat_no": seat, "stack": 1},
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

    completed = service.complete_hand(table_id, {"p1": 0, "p2": 150})
    p1 = next(s for s in completed["seats"] if s["player_id"] == "p1")
    assert p1["status"] == "eliminated"
    assert p1["stack"] == 0

    rebuy = client.post(
        f"/api/v1/tables/{table_id}/rebuy",
        headers={"X-Session-ID": p1_session},
    )
    assert rebuy.status_code == 200
    p1 = next(s for s in rebuy.json()["seats"] if s["player_id"] == "p1")
    assert p1["status"] == "seated"
    assert p1["stack"] == 1000
    assert p1["rebuy_count"] == 1

    client_starts = client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    )
    assert client_starts.status_code == 200
    # Rebuy cannot happen during a hand.
    blocked = client.post(
        f"/api/v1/tables/{table_id}/rebuy",
        headers={"X-Session-ID": p1_session},
    )
    assert blocked.status_code == 409

    # Abort via operator so add-on can be exercised between hands.
    assert client.post(
        f"/api/v1/operator/tables/{table_id}/pause",
        headers={"X-Operator-Key": "operator"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/operator/tables/{table_id}/abort-hand",
        headers={"X-Operator-Key": "operator"},
        json={"reason": "policy test"},
    ).status_code == 200

    addon = client.post(
        f"/api/v1/tables/{table_id}/addon",
        headers={"X-Session-ID": p1_session},
    )
    assert addon.status_code == 200
    p1 = next(s for s in addon.json()["seats"] if s["player_id"] == "p1")
    assert p1["stack"] == 1450


def test_blind_schedule_pause_start_and_reset(env):
    client, db_path, _ = env
    table_id = make_table(client)
    assert configure_tournament(client, table_id).status_code == 200
    headers = {"X-Operator-Key": "operator"}

    paused = client.post(
        f"/api/v1/operator/tables/{table_id}/blind-schedule/pause",
        headers=headers,
    )
    assert paused.status_code == 200
    assert paused.json()["blind_schedule_status"] == "paused"

    conn = sqlite3.connect(db_path)
    try:
        before = conn.execute(
            "SELECT blind_level_started_at FROM runtime_tables WHERE id = ?",
            (table_id,),
        ).fetchone()[0]
    finally:
        conn.close()

    started = client.post(
        f"/api/v1/operator/tables/{table_id}/blind-schedule/start",
        headers=headers,
    )
    assert started.status_code == 200
    assert started.json()["blind_schedule_status"] == "running"
    assert started.json()["blind_level_started_at"] >= before

    reset = client.post(
        f"/api/v1/operator/tables/{table_id}/blind-schedule/reset",
        headers=headers,
    )
    assert reset.status_code == 200
    state = reset.json()
    assert state["blind_schedule_status"] == "paused"
    assert state["blind_level_index"] == 0
    assert state["small_blind"] == 50
    assert state["big_blind"] == 100
