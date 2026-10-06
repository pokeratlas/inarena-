from __future__ import annotations

import importlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "outbox.sqlite3"
    monkeypatch.setenv("INARENA_DB_PATH", str(db_path))
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")

    import app.db as db
    import app.service as service
    import app.main as main

    importlib.reload(db)
    importlib.reload(service)
    importlib.reload(main)

    with TestClient(main.app):
        yield db_path, service


def test_business_mutation_and_outbox_commit_together(env):
    db_path, service = env
    table = service.create_table("Outbox")
    table_id = table["id"]

    service.join_table(table_id, "p1", 1, 1000)

    conn = sqlite3.connect(db_path)
    try:
        seat_count = conn.execute(
            "SELECT COUNT(*) FROM runtime_seats WHERE table_id = ?",
            (table_id,),
        ).fetchone()[0]
        pending = conn.execute(
            """
            SELECT id, event_type, payload_json, dispatched_at
            FROM realtime_outbox
            WHERE table_id = ?
            """,
            (table_id,),
        ).fetchall()
        event_count = conn.execute(
            "SELECT COUNT(*) FROM realtime_events WHERE table_id = ?",
            (table_id,),
        ).fetchone()[0]

        assert seat_count == 1
        assert len(pending) == 1
        assert pending[0][1] == "player_joined"
        assert pending[0][3] is None
        assert event_count == 0

        snapshot = json.loads(pending[0][2])
        assert any(
            seat["player_id"] == "p1" and seat["seat_no"] == 1
            for seat in snapshot["seats"]
        )
    finally:
        conn.close()


def test_outbox_dispatch_is_deduplicated(env):
    db_path, service = env
    table_id = service.create_table("Dispatch")["id"]
    service.join_table(table_id, "p1", 1, 1000)

    first = service.dispatch_table_outbox(table_id)
    second = service.dispatch_table_outbox(table_id)

    assert len(first) == 1
    assert first[0]["event_type"] == "player_joined"
    assert second == []

    conn = sqlite3.connect(db_path)
    try:
        event_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM realtime_events
            WHERE table_id = ? AND event_type = 'player_joined'
            """,
            (table_id,),
        ).fetchone()[0]
        dispatched = conn.execute(
            """
            SELECT COUNT(*)
            FROM realtime_outbox
            WHERE table_id = ? AND dispatched_at IS NOT NULL
            """,
            (table_id,),
        ).fetchone()[0]
        assert event_count == 1
        assert dispatched == 1
    finally:
        conn.close()


def test_failed_mutation_does_not_create_second_outbox_entry(env):
    db_path, service = env
    table_id = service.create_table("Rollback")["id"]
    service.join_table(table_id, "p1", 1, 1000)

    with pytest.raises(service.ConflictError):
        service.join_table(table_id, "p2", 1, 1000)

    conn = sqlite3.connect(db_path)
    try:
        seat_count = conn.execute(
            "SELECT COUNT(*) FROM runtime_seats WHERE table_id = ?",
            (table_id,),
        ).fetchone()[0]
        outbox_count = conn.execute(
            "SELECT COUNT(*) FROM realtime_outbox WHERE table_id = ?",
            (table_id,),
        ).fetchone()[0]
        assert seat_count == 1
        assert outbox_count == 1
    finally:
        conn.close()
