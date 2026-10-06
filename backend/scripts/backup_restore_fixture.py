from __future__ import annotations

import argparse

from app.db import ensure_schema
from app.service import (
    create_table,
    get_table_state,
    join_table,
    list_tables,
    start_hand,
    submit_player_action,
)


MARKER_NAME = "Backup Drill Marker"
EXPECTED_TOTAL_CHIPS = 10_000


def seed() -> None:
    ensure_schema()
    table = create_table(MARKER_NAME)
    table_id = table["id"]

    join_table(table_id, "backup-p1", 1, 5_000)
    join_table(table_id, "backup-p2", 2, 5_000)

    started = start_hand(table_id, 1)
    action_seat = started["active_hand"]["action_seat"]
    actor = next(
        seat["player_id"]
        for seat in started["seats"]
        if seat["seat_no"] == action_seat
    )
    finished = submit_player_action(
        table_id,
        actor,
        "fold",
        0,
    )
    assert finished["active_hand"] is None
    assert sum(seat["stack"] for seat in finished["seats"]) == EXPECTED_TOTAL_CHIPS
    print(table_id)


def verify() -> None:
    ensure_schema()
    tables = [
        table
        for table in list_tables()
        if table["name"] == MARKER_NAME
    ]
    assert len(tables) == 1, tables
    state = get_table_state(tables[0]["id"])

    assert state["active_hand"] is None
    assert len(state["seats"]) == 2
    assert sum(seat["stack"] for seat in state["seats"]) == EXPECTED_TOTAL_CHIPS
    assert state["status"] == "open"

    from app.db import connect

    conn = connect()
    try:
        hand_results = int(
            conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM hand_results
                WHERE table_id = ?
                """,
                (state["id"],),
            ).fetchone()["count"]
        )
        buyins = int(
            conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM table_ledger
                WHERE table_id = ? AND entry_type = 'buyin'
                """,
                (state["id"],),
            ).fetchone()["count"]
        )
        assert hand_results == 1
        assert buyins == 2
    finally:
        conn.close()

    print("INARENA backup/restore verification: PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seed", "verify"))
    args = parser.parse_args()

    if args.command == "seed":
        seed()
    else:
        verify()


if __name__ == "__main__":
    main()
