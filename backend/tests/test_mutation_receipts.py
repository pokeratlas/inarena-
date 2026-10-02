from __future__ import annotations

import importlib
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "receipt-recovery.sqlite3"
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
        yield client, db_path, service


def make_session(service, user_id: str) -> dict:
    return service.create_session(user_id, "test", {})


def make_cash_table(service, table_id_name: str = "Cash") -> str:
    table_id = service.create_table(table_id_name)["id"]
    service.configure_table(
        table_id,
        "cash",
        1000,
        50,
        100,
        [],
        500,
        5000,
    )
    return table_id


def test_crash_after_cash_buyin_recovers_receipt_without_second_debit(env):
    client, db_path, service = env
    table_id = make_cash_table(service)
    session = make_session(service, "cash-player")
    sid = session["session_id"]

    service.operator_adjust_balance("cash-player", 3000)

    payload = {"table_id": table_id, "seat_no": 1, "stack": 1000}
    command = service.reserve_idempotency_command(
        "cash-player", "join-auth", "join-crash", payload
    )
    assert command["state"] == "execute"

    receipt_context = service.build_mutation_receipt_context(
        "cash-player", "join-auth", "join-crash", payload
    )
    committed = service.join_table_with_session(
        table_id, sid, 1, 1000, receipt_context
    )
    assert committed["seats"][0]["stack"] == 1000

    # Simulated process crash: do NOT call store_idempotent_result().
    retried = client.post(
        f"/api/v1/tables/{table_id}/join-auth",
        headers={
            "X-Session-ID": sid,
            "Idempotency-Key": "join-crash",
        },
        json={"seat_no": 1, "stack": 1000},
    )
    assert retried.status_code == 200
    assert retried.json() == committed

    balance = service.get_player_balance(sid)
    assert balance["balance"] == 2000

    conn = sqlite3.connect(db_path)
    try:
        buyins = conn.execute(
            """
            SELECT COUNT(*) FROM table_ledger
            WHERE table_id = ? AND player_id = 'cash-player'
              AND entry_type = 'buyin'
            """,
            (table_id,),
        ).fetchone()[0]
        assert buyins == 1

        status = conn.execute(
            """
            SELECT command_status
            FROM idempotency_records
            WHERE user_id = 'cash-player'
              AND operation = 'join-auth'
              AND idempotency_key = 'join-crash'
            """
        ).fetchone()[0]
        assert status == "completed"
    finally:
        conn.close()


def test_crash_after_player_action_recovers_without_second_hand_action(env):
    client, db_path, service = env
    table_id = make_cash_table(service, "Action")
    p1 = make_session(service, "p1")
    p2 = make_session(service, "p2")

    service.operator_adjust_balance("p1", 2000)
    service.operator_adjust_balance("p2", 2000)
    service.join_table_with_session(table_id, p1["session_id"], 1, 1000)
    service.join_table_with_session(table_id, p2["session_id"], 2, 1000)
    service.start_hand(table_id, 1)

    payload = {
        "table_id": table_id,
        "action": "call",
        "expected_action_no": 0,
        "amount": None,
    }
    assert service.reserve_idempotency_command(
        "p1", "action-auth", "action-crash", payload
    )["state"] == "execute"

    receipt_context = service.build_mutation_receipt_context(
        "p1", "action-auth", "action-crash", payload
    )
    committed = service.submit_player_action_with_session(
        table_id,
        p1["session_id"],
        "call",
        0,
        None,
        receipt_context,
    )

    retried = client.post(
        f"/api/v1/tables/{table_id}/action-auth",
        headers={
            "X-Session-ID": p1["session_id"],
            "Idempotency-Key": "action-crash",
        },
        json={"action": "call", "expected_action_no": 0},
    )
    assert retried.status_code == 200
    assert retried.json() == committed

    conn = sqlite3.connect(db_path)
    try:
        actions = conn.execute(
            "SELECT COUNT(*) FROM hand_actions WHERE table_id = ?",
            (table_id,),
        ).fetchone()[0]
        assert actions == 1
    finally:
        conn.close()


def test_crash_after_cashout_recovers_without_second_credit(env):
    client, db_path, service = env
    table_id = make_cash_table(service, "Cashout")
    session = make_session(service, "cashout-player")
    sid = session["session_id"]

    service.operator_adjust_balance("cashout-player", 3000)
    service.join_table_with_session(table_id, sid, 1, 1000)

    payload = {"table_id": table_id}
    assert service.reserve_idempotency_command(
        "cashout-player", "stand-auth", "stand-crash", payload
    )["state"] == "execute"

    receipt_context = service.build_mutation_receipt_context(
        "cashout-player", "stand-auth", "stand-crash", payload
    )
    committed = service.stand_with_session(
        table_id, sid, receipt_context
    )

    retried = client.post(
        f"/api/v1/tables/{table_id}/stand-auth",
        headers={
            "X-Session-ID": sid,
            "Idempotency-Key": "stand-crash",
        },
    )
    assert retried.status_code == 200
    assert retried.json() == committed
    assert service.get_player_balance(sid)["balance"] == 3000

    conn = sqlite3.connect(db_path)
    try:
        cashouts = conn.execute(
            """
            SELECT COUNT(*) FROM table_ledger
            WHERE table_id = ? AND player_id = 'cashout-player'
              AND entry_type = 'cashout'
            """,
            (table_id,),
        ).fetchone()[0]
        assert cashouts == 1
    finally:
        conn.close()
