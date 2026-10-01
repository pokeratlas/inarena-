from __future__ import annotations

import importlib
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "waitlist.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))
    monkeypatch.setenv("INARENA_OPERATOR_KEY", "operator")
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")
    monkeypatch.setenv("INARENA_SEAT_RESERVATION_SECONDS", "20")

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as client:
        yield client, db_path


def session(client: TestClient, user_id: str) -> str:
    r = client.post(
        "/api/v1/sessions",
        json={"user_id": user_id, "provider": "test", "data": {}},
    )
    assert r.status_code == 201
    return r.json()["session_id"]


def cash_table(client: TestClient) -> str:
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Waitlist"},
    ).json()["id"]
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
    return table_id


def fill_table(client: TestClient, table_id: str):
    for seat_no in range(1, 10):
        r = client.post(
            f"/api/v1/tables/{table_id}/join",
            json={
                "player_id": f"p{seat_no}",
                "seat_no": seat_no,
                "stack": 2000,
            },
        )
        assert r.status_code == 200


def test_waitlist_is_fifo_and_freed_seat_is_reserved(env):
    client, _ = env
    table_id = cash_table(client)
    fill_table(client, table_id)

    s1 = session(client, "w1")
    s2 = session(client, "w2")

    first = client.post(
        f"/api/v1/tables/{table_id}/waitlist",
        headers={"X-Session-ID": s1},
    )
    second = client.post(
        f"/api/v1/tables/{table_id}/waitlist",
        headers={"X-Session-ID": s2},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["position"] == 1
    assert second.json()["position"] == 2

    left = client.post(
        f"/api/v1/tables/{table_id}/stand",
        json={"player_id": "p4"},
    )
    assert left.status_code == 200

    w1 = client.get(
        f"/api/v1/tables/{table_id}/waitlist",
        headers={"X-Session-ID": s1},
    ).json()
    w2 = client.get(
        f"/api/v1/tables/{table_id}/waitlist",
        headers={"X-Session-ID": s2},
    ).json()

    assert w1["status"] == "reserved"
    assert w1["reservation"]["seat_no"] == 4
    assert w2["status"] == "waiting"
    assert w2["position"] == 1


def test_expired_reservation_moves_to_next_waitlist_player(env):
    client, db_path = env
    table_id = cash_table(client)
    fill_table(client, table_id)

    s1 = session(client, "w1")
    s2 = session(client, "w2")
    client.post(
        f"/api/v1/tables/{table_id}/waitlist",
        headers={"X-Session-ID": s1},
    )
    client.post(
        f"/api/v1/tables/{table_id}/waitlist",
        headers={"X-Session-ID": s2},
    )
    client.post(
        f"/api/v1/tables/{table_id}/stand",
        json={"player_id": "p1"},
    )

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            UPDATE seat_reservations
            SET expires_at_epoch = ?
            WHERE table_id = ? AND status = 'active'
            """,
            (int(time.time()) - 1, table_id),
        )
        conn.commit()
    finally:
        conn.close()

    refreshed = client.post(
        f"/api/v1/operator/tables/{table_id}/waitlist/refresh",
        headers={"X-Operator-Key": "operator"},
    )
    assert refreshed.status_code == 200

    w1 = client.get(
        f"/api/v1/tables/{table_id}/waitlist",
        headers={"X-Session-ID": s1},
    ).json()
    w2 = client.get(
        f"/api/v1/tables/{table_id}/waitlist",
        headers={"X-Session-ID": s2},
    ).json()

    assert w1["status"] == "expired"
    assert w2["status"] == "reserved"
    assert w2["reservation"]["seat_no"] == 1


def test_reserved_player_can_claim_exact_seat(env):
    client, _ = env
    table_id = cash_table(client)
    fill_table(client, table_id)

    sid = session(client, "w1")
    client.post(
        f"/api/v1/tables/{table_id}/waitlist",
        headers={"X-Session-ID": sid},
    )
    client.post(
        f"/api/v1/tables/{table_id}/stand",
        json={"player_id": "p7"},
    )

    status = client.get(
        f"/api/v1/tables/{table_id}/waitlist",
        headers={"X-Session-ID": sid},
    ).json()
    reservation = status["reservation"]
    assert reservation["seat_no"] == 7

    claimed = client.post(
        f"/api/v1/tables/{table_id}/reservations/claim",
        headers={"X-Session-ID": sid},
        json={
            "reservation_id": reservation["id"],
            "stack": 2000,
        },
    )
    assert claimed.status_code == 200
    seats = claimed.json()["seats"]
    assert any(
        seat["seat_no"] == 7 and seat["player_id"] == "w1"
        for seat in seats
    )

    after = client.get(
        f"/api/v1/tables/{table_id}/waitlist",
        headers={"X-Session-ID": sid},
    ).json()
    assert after["status"] == "seated"
    assert after["reservation"] is None
