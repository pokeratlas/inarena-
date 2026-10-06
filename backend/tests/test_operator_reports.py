from __future__ import annotations

import csv
import importlib
import io
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "reports.sqlite3"
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


def make_cash_table(client: TestClient) -> str:
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Report Cash"},
    ).json()["id"]
    response = client.post(
        f"/api/v1/operator/tables/{table_id}/configure",
        headers={"X-Operator-Key": "operator"},
        json={
            "table_mode": "cash",
            "starting_stack": 2000,
            "small_blind": 50,
            "big_blind": 100,
            "blind_schedule": [],
            "cash_buyin_min": 500,
            "cash_buyin_max": 5000,
        },
    )
    assert response.status_code == 200
    return table_id


def make_tournament(client: TestClient) -> str:
    table_id = client.post(
        "/api/v1/tables",
        json={"name": "Report Tournament"},
    ).json()["id"]
    response = client.post(
        f"/api/v1/operator/tables/{table_id}/configure",
        headers={"X-Operator-Key": "operator"},
        json={
            "table_mode": "tournament",
            "starting_stack": 1000,
            "small_blind": 50,
            "big_blind": 100,
            "blind_schedule": [
                {
                    "small_blind": 50,
                    "big_blind": 100,
                    "duration_seconds": 60,
                }
            ],
            "cash_buyin_min": 500,
            "cash_buyin_max": 5000,
            "rebuy_enabled": True,
            "rebuy_stack": 1000,
            "rebuy_max_per_player": 1,
            "addon_enabled": True,
            "addon_stack": 500,
        },
    )
    assert response.status_code == 200
    return table_id


def test_reports_require_operator_auth(env):
    client, _, _ = env
    table_id = make_cash_table(client)

    response = client.get(
        f"/api/v1/operator/reports/tables/{table_id}/ledger"
    )
    assert response.status_code == 401


def test_ledger_json_and_csv_are_deterministic(env):
    client, _, _ = env
    table_id = make_cash_table(client)

    assert client.post(
        f"/api/v1/tables/{table_id}/join",
        json={"player_id": "p1", "seat_no": 1, "stack": 1200},
    ).status_code == 200
    assert client.post(
        f"/api/v1/tables/{table_id}/stand",
        json={"player_id": "p1"},
    ).status_code == 200

    headers = {"X-Operator-Key": "operator"}
    json_response = client.get(
        f"/api/v1/operator/reports/tables/{table_id}/ledger",
        headers=headers,
    )
    assert json_response.status_code == 200
    rows = json_response.json()
    assert [row["entry_type"] for row in rows] == ["buyin", "cashout"]
    assert [row["amount"] for row in rows] == [1200, 1200]

    csv_response = client.get(
        f"/api/v1/operator/reports/tables/{table_id}/ledger",
        headers=headers,
        params={"format": "csv"},
    )
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    parsed = list(csv.reader(io.StringIO(csv_response.text)))
    assert parsed[0] == [
        "table_id",
        "player_id",
        "entry_type",
        "amount",
        "details",
        "created_at",
    ]
    assert parsed[1][2] == "buyin"
    assert parsed[2][2] == "cashout"


def test_tournament_registration_and_results_reports(env):
    client, db_path, _ = env
    table_id = make_tournament(client)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO tournament_registrations(
                table_id, user_id, status, registered_at
            ) VALUES (?, 'p1', 'registered', '2026-10-01 10:00:00')
            """,
            (table_id,),
        )
        conn.execute(
            """
            INSERT INTO tournament_registrations(
                table_id, user_id, status, registered_at
            ) VALUES (?, 'p2', 'registered', '2026-10-01 10:01:00')
            """,
            (table_id,),
        )
        conn.execute(
            """
            INSERT INTO runtime_seats(
                table_id, seat_no, player_id, stack, status,
                rebuy_count, addon_used, finish_place
            ) VALUES (?, 1, 'p1', 0, 'eliminated', 0, 0, 2)
            """,
            (table_id,),
        )
        conn.execute(
            """
            INSERT INTO runtime_seats(
                table_id, seat_no, player_id, stack, status,
                rebuy_count, addon_used, finish_place
            ) VALUES (?, 2, 'p2', 2000, 'seated', 1, 1, 1)
            """,
            (table_id,),
        )
        conn.execute(
            """
            UPDATE runtime_tables
            SET winner_player_id = 'p2',
                finished_at = '2026-10-01 12:00:00',
                tournament_status = 'finished'
            WHERE id = ?
            """,
            (table_id,),
        )
        conn.commit()
    finally:
        conn.close()

    headers = {"X-Operator-Key": "operator"}
    registrations = client.get(
        f"/api/v1/operator/reports/tournaments/{table_id}/registrations",
        headers=headers,
    )
    assert registrations.status_code == 200
    assert [row["user_id"] for row in registrations.json()] == ["p1", "p2"]

    results = client.get(
        f"/api/v1/operator/reports/tournaments/{table_id}/results",
        headers=headers,
    )
    assert results.status_code == 200
    rows = results.json()
    assert [row["finish_place"] for row in rows] == [1, 2]
    assert rows[0]["player_id"] == "p2"
    assert rows[0]["winner"] is True
    assert rows[0]["rebuy_count"] == 1
    assert rows[0]["addon_used"] is True


def test_audit_csv_serializes_nested_details_as_compact_json(env):
    client, _, service = env
    table_id = make_cash_table(client)
    service.operator_adjust_balance("player", 1000)

    headers = {"X-Operator-Key": "operator"}
    response = client.get(
        "/api/v1/operator/reports/audit",
        headers=headers,
        params={"format": "csv"},
    )
    assert response.status_code == 200

    rows = list(csv.DictReader(io.StringIO(response.text)))
    balance_rows = [
        row for row in rows if row["action"] == "balance_adjusted"
    ]
    assert len(balance_rows) == 1
    details = balance_rows[0]["details"]
    assert " " not in details
    decoded = json.loads(details)
    assert decoded["user_id"] == "player"
    assert decoded["delta"] == 1000


def test_invalid_report_format_returns_400(env):
    client, _, _ = env
    table_id = make_cash_table(client)

    response = client.get(
        f"/api/v1/operator/reports/tables/{table_id}/ledger",
        headers={"X-Operator-Key": "operator"},
        params={"format": "xml"},
    )
    assert response.status_code == 400
