from __future__ import annotations

import importlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "action-settlement-outbox.sqlite3"
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


def test_final_action_settles_and_enqueues_final_snapshot_atomically(env):
    client, db_path = env
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Atomic showdown"},
    ).json()["id"]

    for player_id, seat_no in (("p1", 1), ("p2", 2)):
        assert client.post(
            f"/api/v1/tables/{table_id}/join",
            json={
                "player_id": player_id,
                "seat_no": seat_no,
                "stack": 1000,
            },
        ).status_code == 200

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

    conn = sqlite3.connect(db_path)
    try:
        active = conn.execute(
            "SELECT COUNT(*) FROM active_hands WHERE table_id = ?",
            (table_id,),
        ).fetchone()[0]
        results = conn.execute(
            "SELECT COUNT(*) FROM hand_results WHERE table_id = ?",
            (table_id,),
        ).fetchone()[0]
        outbox = conn.execute(
            """
            SELECT event_type, payload_json
            FROM realtime_outbox
            WHERE table_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (table_id,),
        ).fetchone()

        assert active == 0
        assert results == 1
        assert outbox is not None
        assert outbox[0] == "hand_completed"

        payload = json.loads(outbox[1])
        assert payload["active_hand"] is None
        assert payload["status"] == "open"
    finally:
        conn.close()
