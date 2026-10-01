from __future__ import annotations

import json
import uuid

from .db import connect, transaction


class NotFoundError(RuntimeError):
    pass


class ConflictError(RuntimeError):
    pass


def create_table(name: str) -> dict:
    table_id = str(uuid.uuid4())
    with transaction() as conn:
        conn.execute(
            "INSERT INTO runtime_tables(id, name, status) VALUES (?, ?, 'open')",
            (table_id, name.strip() or "INARENA Table"),
        )
    return get_table_state(table_id)


def list_tables() -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT id FROM runtime_tables ORDER BY created_at DESC"
        ).fetchall()
        return [get_table_state(row["id"]) for row in rows]
    finally:
        conn.close()


def _require_table(conn, table_id: str) -> None:
    row = conn.execute("SELECT id FROM runtime_tables WHERE id = ?", (table_id,)).fetchone()
    if row is None:
        raise NotFoundError("table not found")


def join_table(table_id: str, player_id: str, seat_no: int, stack: int) -> dict:
    if seat_no < 1 or seat_no > 9:
        raise ConflictError("seat_no must be between 1 and 9")
    if stack < 0:
        raise ConflictError("stack must be non-negative")

    with transaction() as conn:
        _require_table(conn, table_id)
        try:
            conn.execute(
                """
                INSERT INTO runtime_seats(table_id, seat_no, player_id, stack, status)
                VALUES (?, ?, ?, ?, 'seated')
                """,
                (table_id, seat_no, player_id, stack),
            )
        except Exception as exc:
            raise ConflictError("seat or player already occupied") from exc
        conn.execute(
            "UPDATE runtime_tables SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (table_id,),
        )
    return get_table_state(table_id)


def stand(table_id: str, player_id: str) -> dict:
    with transaction() as conn:
        _require_table(conn, table_id)
        cur = conn.execute(
            "DELETE FROM runtime_seats WHERE table_id = ? AND player_id = ?",
            (table_id, player_id),
        )
        if cur.rowcount == 0:
            raise NotFoundError("player is not seated")
        conn.execute(
            "UPDATE runtime_tables SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (table_id,),
        )
    return get_table_state(table_id)


def start_hand(table_id: str, button_seat: int | None = None) -> dict:
    with transaction() as conn:
        _require_table(conn, table_id)
        existing = conn.execute(
            "SELECT hand_id FROM active_hands WHERE table_id = ?", (table_id,)
        ).fetchone()
        if existing:
            raise ConflictError("active hand already exists")

        seats = conn.execute(
            """
            SELECT seat_no, player_id, stack
            FROM runtime_seats
            WHERE table_id = ? AND status = 'seated'
            ORDER BY seat_no
            """,
            (table_id,),
        ).fetchall()
        if len(seats) < 2:
            raise ConflictError("at least two seated players are required")

        seat_numbers = [row["seat_no"] for row in seats]
        button = button_seat if button_seat in seat_numbers else seat_numbers[0]
        action = next((s for s in seat_numbers if s > button), seat_numbers[0])
        hand_id = str(uuid.uuid4())
        state = {
            "hand_id": hand_id,
            "street": "preflop",
            "pot": 0,
            "button_seat": button,
            "action_seat": action,
            "players": [
                {"seat_no": row["seat_no"], "player_id": row["player_id"], "stack": row["stack"]}
                for row in seats
            ],
        }
        conn.execute(
            """
            INSERT INTO active_hands(
                table_id, hand_id, street, pot, button_seat, action_seat, state_json
            ) VALUES (?, ?, 'preflop', 0, ?, ?, ?)
            """,
            (table_id, hand_id, button, action, json.dumps(state, separators=(",", ":"))),
        )
        conn.execute(
            "UPDATE runtime_tables SET status = 'playing', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (table_id,),
        )
    return get_table_state(table_id)


def complete_hand(table_id: str) -> dict:
    with transaction() as conn:
        _require_table(conn, table_id)
        cur = conn.execute("DELETE FROM active_hands WHERE table_id = ?", (table_id,))
        if cur.rowcount == 0:
            raise NotFoundError("no active hand")
        conn.execute(
            "UPDATE runtime_tables SET status = 'open', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (table_id,),
        )
    return get_table_state(table_id)


def get_table_state(table_id: str) -> dict:
    conn = connect()
    try:
        table = conn.execute(
            "SELECT id, name, status, created_at, updated_at FROM runtime_tables WHERE id = ?",
            (table_id,),
        ).fetchone()
        if table is None:
            raise NotFoundError("table not found")

        seats = conn.execute(
            """
            SELECT seat_no, player_id, stack, status, updated_at
            FROM runtime_seats
            WHERE table_id = ?
            ORDER BY seat_no
            """,
            (table_id,),
        ).fetchall()
        hand = conn.execute(
            """
            SELECT hand_id, street, pot, button_seat, action_seat, state_json,
                   started_at, updated_at
            FROM active_hands
            WHERE table_id = ?
            """,
            (table_id,),
        ).fetchone()

        return {
            "id": table["id"],
            "name": table["name"],
            "status": table["status"],
            "created_at": table["created_at"],
            "updated_at": table["updated_at"],
            "seats": [dict(row) for row in seats],
            "active_hand": None
            if hand is None
            else {
                "hand_id": hand["hand_id"],
                "street": hand["street"],
                "pot": hand["pot"],
                "button_seat": hand["button_seat"],
                "action_seat": hand["action_seat"],
                "state": json.loads(hand["state_json"]),
                "started_at": hand["started_at"],
                "updated_at": hand["updated_at"],
            },
        }
    finally:
        conn.close()
