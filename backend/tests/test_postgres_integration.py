from __future__ import annotations

import importlib
import os
import uuid

import pytest


POSTGRES_URL = os.getenv("INARENA_TEST_POSTGRES_URL")


@pytest.mark.skipif(
    not POSTGRES_URL,
    reason="INARENA_TEST_POSTGRES_URL is not configured",
)
def test_postgres_runtime_smoke(monkeypatch):
    monkeypatch.setenv("INARENA_DATABASE_URL", POSTGRES_URL)
    monkeypatch.delenv("INARENA_DB_PATH", raising=False)
    monkeypatch.setenv("INARENA_ENV", "test")
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")

    import app.db as db
    import app.service as service

    importlib.reload(db)
    importlib.reload(service)

    assert db.database_backend() == "postgresql"
    db.ensure_schema()
    assert db.schema_version() == db.SCHEMA_VERSION

    suffix = uuid.uuid4().hex[:8]
    table_id = service.create_table(f"Postgres {suffix}")["id"]

    first = service.join_table(table_id, f"p1-{suffix}", 1, 2000)
    second = service.join_table(table_id, f"p2-{suffix}", 2, 2000)
    assert len(first["seats"]) == 1
    assert len(second["seats"]) == 2

    started = service.start_hand(table_id, button_seat=1)
    hand = started["active_hand"]
    assert hand is not None
    assert hand["pot"] == 150
    assert hand["action_seat"] == 1

    acted = service.submit_player_action(
        table_id,
        f"p1-{suffix}",
        "call",
        0,
    )
    assert acted["active_hand"] is not None
    assert acted["active_hand"]["pot"] == 200

    events = service.dispatch_table_outbox(table_id)
    event_types = [event["event_type"] for event in events]
    assert event_types.count("player_joined") == 2
    assert "hand_started" in event_types

    state = service.get_table_state(table_id)
    assert state["id"] == table_id
    assert len(state["seats"]) == 2
