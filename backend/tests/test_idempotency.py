from __future__ import annotations

import importlib
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "idempotency.sqlite3"
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
        yield client, db_path


def session(client: TestClient, user_id: str) -> str:
    r = client.post(
        "/api/v1/sessions",
        json={"user_id": user_id, "provider": "test", "data": {}},
    )
    assert r.status_code == 201
    return r.json()["session_id"]


def table(client: TestClient, mode: str = "cash") -> str:
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Idempotency"},
    ).json()["id"]
    payload = {
        "table_mode": mode,
        "starting_stack": 1000,
        "small_blind": 50,
        "big_blind": 100,
        "blind_schedule": (
            [{"small_blind": 50, "big_blind": 100, "duration_seconds": 60}]
            if mode == "tournament"
            else []
        ),
        "cash_buyin_min": 500,
        "cash_buyin_max": 5000,
        "rebuy_enabled": mode == "tournament",
        "rebuy_stack": 1000 if mode == "tournament" else 0,
        "rebuy_max_per_player": 1 if mode == "tournament" else 0,
        "addon_enabled": mode == "tournament",
        "addon_stack": 500 if mode == "tournament" else 0,
    }
    r = client.post(
        f"/api/v1/operator/tables/{table_id}/configure",
        headers={"X-Operator-Key": "operator"},
        json=payload,
    )
    assert r.status_code == 200
    return table_id


def test_join_replay_does_not_duplicate_buyin_ledger(env):
    client, db_path = env
    table_id = table(client)
    sid = session(client, "p1")
    headers = {
        "X-Session-ID": sid,
        "Idempotency-Key": "join-1",
    }
    payload = {"seat_no": 1, "stack": 1000}

    first = client.post(
        f"/api/v1/tables/{table_id}/join-auth",
        headers=headers,
        json=payload,
    )
    second = client.post(
        f"/api/v1/tables/{table_id}/join-auth",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM table_ledger
            WHERE table_id = ? AND player_id = 'p1'
              AND entry_type = 'buyin'
            """,
            (table_id,),
        ).fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_same_idempotency_key_with_different_payload_is_rejected(env):
    client, _ = env
    table_id = table(client)
    sid = session(client, "p1")
    headers = {
        "X-Session-ID": sid,
        "Idempotency-Key": "join-different",
    }

    first = client.post(
        f"/api/v1/tables/{table_id}/join-auth",
        headers=headers,
        json={"seat_no": 1, "stack": 1000},
    )
    assert first.status_code == 200

    changed = client.post(
        f"/api/v1/tables/{table_id}/join-auth",
        headers=headers,
        json={"seat_no": 2, "stack": 1000},
    )
    assert changed.status_code == 409


def test_player_action_replay_does_not_append_second_hand_action(env):
    client, db_path = env
    table_id = table(client)
    p1 = session(client, "p1")
    p2 = session(client, "p2")

    for sid, seat in ((p1, 1), (p2, 2)):
        assert client.post(
            f"/api/v1/tables/{table_id}/join-auth",
            headers={"X-Session-ID": sid},
            json={"seat_no": seat, "stack": 1000},
        ).status_code == 200

    assert client.post(
        f"/api/v1/tables/{table_id}/start-hand",
        json={"button_seat": 1},
    ).status_code == 200

    headers = {
        "X-Session-ID": p1,
        "Idempotency-Key": "action-1",
    }
    payload = {
        "action": "call",
        "expected_action_no": 0,
    }

    first = client.post(
        f"/api/v1/tables/{table_id}/action-auth",
        headers=headers,
        json=payload,
    )
    second = client.post(
        f"/api/v1/tables/{table_id}/action-auth",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM hand_actions WHERE table_id = ?",
            (table_id,),
        ).fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_waitlist_replay_keeps_single_queue_entry(env):
    client, db_path = env
    table_id = table(client)
    sid = session(client, "waiter")
    headers = {
        "X-Session-ID": sid,
        "Idempotency-Key": "wait-1",
    }

    first = client.post(
        f"/api/v1/tables/{table_id}/waitlist",
        headers=headers,
    )
    second = client.post(
        f"/api/v1/tables/{table_id}/waitlist",
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM cash_waitlist
            WHERE table_id = ? AND user_id = 'waiter'
            """,
            (table_id,),
        ).fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_addon_replay_does_not_duplicate_chips_or_ledger(env):
    client, db_path = env
    table_id = table(client, "tournament")
    sid = session(client, "p1")

    joined = client.post(
        f"/api/v1/tables/{table_id}/join-auth",
        headers={"X-Session-ID": sid},
        json={"seat_no": 1, "stack": 1},
    )
    assert joined.status_code == 200

    headers = {
        "X-Session-ID": sid,
        "Idempotency-Key": "addon-1",
    }
    first = client.post(
        f"/api/v1/tables/{table_id}/addon",
        headers=headers,
    )
    second = client.post(
        f"/api/v1/tables/{table_id}/addon",
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    seat = first.json()["seats"][0]
    assert seat["stack"] == 1500

    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM table_ledger
            WHERE table_id = ? AND player_id = 'p1'
              AND entry_type = 'addon'
            """,
            (table_id,),
        ).fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_idempotency_replay_survives_app_reload(tmp_path, monkeypatch):
    db_path = tmp_path / "idempotency-restart.sqlite3"
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
        table_id = table(client)
        sid = session(client, "restart-player")
        headers = {
            "X-Session-ID": sid,
            "Idempotency-Key": "restart-join",
        }
        payload = {"seat_no": 1, "stack": 1000}
        first = client.post(
            f"/api/v1/tables/{table_id}/join-auth",
            headers=headers,
            json=payload,
        )
        assert first.status_code == 200
        first_body = first.json()

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app) as client:
        replay = client.post(
            f"/api/v1/tables/{table_id}/join-auth",
            headers=headers,
            json=payload,
        )
        assert replay.status_code == 200
        assert replay.json() == first_body

        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute(
                """
                SELECT COUNT(*)
                FROM table_ledger
                WHERE table_id = ? AND player_id = 'restart-player'
                  AND entry_type = 'buyin'
                """,
                (table_id,),
            ).fetchone()[0]
            assert count == 1
        finally:
            conn.close()
