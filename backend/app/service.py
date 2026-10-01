from __future__ import annotations

import json
import secrets
import uuid

from .db import connect, transaction
from .poker import evaluate_seven


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
    row = conn.execute(
        "SELECT id FROM runtime_tables WHERE id = ?", (table_id,)
    ).fetchone()
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
        active = conn.execute(
            "SELECT 1 FROM active_hands WHERE table_id = ?", (table_id,)
        ).fetchone()
        if active:
            raise ConflictError("cannot stand during an active hand")
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
        table = conn.execute(
            """
            SELECT small_blind, big_blind, last_button_seat
            FROM runtime_tables
            WHERE id = ?
            """,
            (table_id,),
        ).fetchone()

        existing = conn.execute(
            "SELECT hand_id FROM active_hands WHERE table_id = ?", (table_id,)
        ).fetchone()
        if existing:
            raise ConflictError("active hand already exists")

        seat_rows = conn.execute(
            """
            SELECT seat_no, player_id, stack
            FROM runtime_seats
            WHERE table_id = ? AND status = 'seated' AND stack > 0
            ORDER BY seat_no
            """,
            (table_id,),
        ).fetchall()
        seats = [dict(row) for row in seat_rows]
        if len(seats) < 2:
            raise ConflictError("at least two funded players are required")

        seat_numbers = [row["seat_no"] for row in seats]
        if button_seat in seat_numbers:
            button = int(button_seat)
        elif table["last_button_seat"] in seat_numbers:
            button = _clockwise_first(
                seats, int(table["last_button_seat"])
            )["seat_no"]
        else:
            button = seat_numbers[0]

        if len(seats) == 2:
            sb_row = next(row for row in seats if row["seat_no"] == button)
            bb_row = _clockwise_first(seats, button)
            preflop_first = sb_row
        else:
            sb_row = _clockwise_first(seats, button)
            bb_row = _clockwise_first(seats, sb_row["seat_no"])
            preflop_first = _clockwise_first(seats, bb_row["seat_no"])

        small_blind = int(table["small_blind"])
        big_blind = int(table["big_blind"])
        hand_id = str(uuid.uuid4())

        deck = [
            f"{rank}{suit}"
            for rank in "23456789TJQKA"
            for suit in "cdhs"
        ]
        secrets.SystemRandom().shuffle(deck)
        private_cards: dict[str, list[str]] = {}
        for row in seats:
            private_cards[row["player_id"]] = [deck.pop(), deck.pop()]

        contributions = {row["player_id"]: 0 for row in seats}
        street_contributions = {row["player_id"]: 0 for row in seats}

        sb_paid = min(small_blind, int(sb_row["stack"]))
        bb_paid = min(big_blind, int(bb_row["stack"]))
        for row, paid in ((sb_row, sb_paid), (bb_row, bb_paid)):
            if paid:
                conn.execute(
                    """
                    UPDATE runtime_seats
                    SET stack = stack - ?, updated_at = CURRENT_TIMESTAMP
                    WHERE table_id = ? AND player_id = ?
                    """,
                    (paid, table_id, row["player_id"]),
                )
                contributions[row["player_id"]] += paid
                street_contributions[row["player_id"]] += paid
                row["stack"] -= paid

        refreshed = conn.execute(
            """
            SELECT seat_no, player_id, stack
            FROM runtime_seats
            WHERE table_id = ? AND status = 'seated'
            ORDER BY seat_no
            """,
            (table_id,),
        ).fetchall()
        current_seats = [dict(row) for row in refreshed]
        actionable = [row for row in current_seats if int(row["stack"]) > 0]
        if actionable:
            if preflop_first["player_id"] in {
                row["player_id"] for row in actionable
            }:
                action = preflop_first["seat_no"]
            else:
                action = _clockwise_first(
                    actionable, preflop_first["seat_no"]
                )["seat_no"]
        else:
            action = None

        pot = sb_paid + bb_paid
        state = {
            "hand_id": hand_id,
            "street": "preflop",
            "pot": pot,
            "button_seat": button,
            "small_blind_seat": sb_row["seat_no"],
            "big_blind_seat": bb_row["seat_no"],
            "small_blind": small_blind,
            "big_blind": big_blind,
            "action_seat": action,
            "action_no": 0,
            "current_bet": max(sb_paid, bb_paid),
            "min_raise": big_blind,
            "contributions": contributions,
            "street_contributions": street_contributions,
            "acted": [],
            "folded": [],
            "board": [],
            "showdown_pending": False,
            "players": [
                {
                    "seat_no": row["seat_no"],
                    "player_id": row["player_id"],
                    "stack": row["stack"],
                }
                for row in current_seats
            ],
        }

        conn.execute(
            """
            INSERT INTO hand_secrets(hand_id, table_id, deck_json)
            VALUES (?, ?, ?)
            """,
            (hand_id, table_id, json.dumps(deck, separators=(",", ":"))),
        )
        for player_id, cards in private_cards.items():
            conn.execute(
                """
                INSERT INTO hand_private_cards(
                    hand_id, table_id, player_id, cards_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    hand_id,
                    table_id,
                    player_id,
                    json.dumps(cards, separators=(",", ":")),
                ),
            )

        conn.execute(
            """
            INSERT INTO active_hands(
                table_id, hand_id, street, pot, button_seat, action_seat, state_json
            ) VALUES (?, ?, 'preflop', ?, ?, ?, ?)
            """,
            (
                table_id,
                hand_id,
                pot,
                button,
                action,
                json.dumps(state, separators=(",", ":")),
            ),
        )
        conn.execute(
            """
            UPDATE runtime_tables
            SET status = 'playing',
                last_button_seat = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (button, table_id),
        )
    return get_table_state(table_id)


def _draw_from_deck(conn, hand_id: str, count: int) -> list[str]:
    row = conn.execute(
        "SELECT deck_json FROM hand_secrets WHERE hand_id = ?",
        (hand_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("hand deck not found")

    deck = json.loads(row["deck_json"])
    if len(deck) < count:
        raise ConflictError("not enough cards in deck")
    cards = [deck.pop() for _ in range(count)]
    conn.execute(
        "UPDATE hand_secrets SET deck_json = ? WHERE hand_id = ?",
        (json.dumps(deck, separators=(",", ":")), hand_id),
    )
    return cards


def _clockwise_first(rows, after_seat: int):
    later = [row for row in rows if row["seat_no"] > after_seat]
    return later[0] if later else rows[0]


def submit_player_action(
    table_id: str,
    player_id: str,
    action: str,
    expected_action_no: int,
    amount: int | None = None,
) -> dict:
    allowed = {"fold", "check", "call", "bet", "raise"}
    if action not in allowed:
        raise ConflictError("unsupported player action")

    with transaction() as conn:
        _require_table(conn, table_id)
        table = conn.execute(
            "SELECT status FROM runtime_tables WHERE id = ?", (table_id,)
        ).fetchone()
        if table["status"] != "playing":
            raise ConflictError("table is not accepting player actions")

        hand = conn.execute(
            """
            SELECT hand_id, pot, action_seat, state_json
            FROM active_hands
            WHERE table_id = ?
            """,
            (table_id,),
        ).fetchone()
        if hand is None:
            raise NotFoundError("no active hand")

        state = json.loads(hand["state_json"])
        if state.get("showdown_pending"):
            raise ConflictError("hand is waiting for settlement")

        action_no = int(state.get("action_no", 0))
        if expected_action_no != action_no:
            raise ConflictError("stale action sequence")

        seat = conn.execute(
            """
            SELECT seat_no, stack
            FROM runtime_seats
            WHERE table_id = ? AND player_id = ? AND status = 'seated'
            """,
            (table_id, player_id),
        ).fetchone()
        if seat is None:
            raise NotFoundError("player is not seated")
        if seat["seat_no"] != hand["action_seat"]:
            raise ConflictError("not this player's turn")

        contributions = dict(state.get("contributions", {}))
        street_contributions = dict(state.get("street_contributions", {}))
        folded = set(state.get("folded", []))
        acted = set(state.get("acted", []))
        current_bet = int(state.get("current_bet", 0))
        min_raise = int(state.get("min_raise", state.get("big_blind", 1)))
        player_street = int(street_contributions.get(player_id, 0))
        total_contribution = int(contributions.get(player_id, 0))
        stack = int(seat["stack"])
        paid = 0

        if action == "fold":
            folded.add(player_id)
            acted.add(player_id)
        elif action == "check":
            if player_street != current_bet:
                raise ConflictError("cannot check facing a bet")
            acted.add(player_id)
        elif action == "call":
            due = max(0, current_bet - player_street)
            if due == 0:
                raise ConflictError("nothing to call")
            paid = min(due, stack)
            acted.add(player_id)
        else:
            if amount is None or amount < 0:
                raise ConflictError("amount is required")
            target = int(amount)
            if target <= current_bet:
                raise ConflictError("bet or raise must exceed current bet")
            paid = target - player_street
            if paid <= 0 or paid > stack:
                raise ConflictError("insufficient stack for action")

            raise_size = target - current_bet
            is_all_in = paid == stack
            if current_bet == 0:
                full_raise = target >= min_raise
            else:
                full_raise = raise_size >= min_raise

            if not full_raise and not is_all_in:
                raise ConflictError("raise is below minimum")

            current_bet = target
            if full_raise:
                min_raise = target if state.get("current_bet", 0) == 0 else raise_size
                acted = {player_id}
            else:
                acted.add(player_id)

        new_stack = stack
        if paid:
            new_stack = stack - paid
            street_contributions[player_id] = player_street + paid
            contributions[player_id] = total_contribution + paid
            conn.execute(
                """
                UPDATE runtime_seats
                SET stack = ?, updated_at = CURRENT_TIMESTAMP
                WHERE table_id = ? AND player_id = ?
                """,
                (new_stack, table_id, player_id),
            )
        else:
            street_contributions.setdefault(player_id, player_street)
            contributions.setdefault(player_id, total_contribution)

        seats = conn.execute(
            """
            SELECT seat_no, player_id, stack
            FROM runtime_seats
            WHERE table_id = ? AND status = 'seated'
            ORDER BY seat_no
            """,
            (table_id,),
        ).fetchall()
        participants = [
            row for row in seats if row["player_id"] not in folded
        ]
        actionable = [
            row for row in participants if int(row["stack"]) > 0
        ]

        next_action_no = action_no + 1
        next_pot = int(hand["pot"]) + paid
        street = str(state.get("street", "preflop"))
        board = list(state.get("board", []))
        showdown_pending = False
        auto_winner: str | None = None
        next_seat: int | None = None

        if len(participants) <= 1:
            next_seat = None
            auto_winner = (
                participants[0]["player_id"] if participants else None
            )
            state["uncontested_winner"] = auto_winner
        else:
            round_complete = (
                all(row["player_id"] in acted for row in actionable)
                and all(
                    int(street_contributions.get(row["player_id"], 0))
                    == current_bet
                    for row in actionable
                )
            )

            if round_complete:
                if street == "river":
                    showdown_pending = True
                elif len(actionable) <= 1:
                    missing = 5 - len(board)
                    if missing > 0:
                        board.extend(_draw_from_deck(conn, hand["hand_id"], missing))
                    street = "river"
                    showdown_pending = True
                else:
                    if street == "preflop":
                        board.extend(_draw_from_deck(conn, hand["hand_id"], 3))
                        street = "flop"
                    elif street == "flop":
                        board.extend(_draw_from_deck(conn, hand["hand_id"], 1))
                        street = "turn"
                    elif street == "turn":
                        board.extend(_draw_from_deck(conn, hand["hand_id"], 1))
                        street = "river"

                    current_bet = 0
                    min_raise = int(state.get("big_blind", min_raise))
                    street_contributions = {
                        row["player_id"]: 0 for row in participants
                    }
                    acted = set()
                    available = [
                        row for row in participants if int(row["stack"]) > 0
                    ]
                    if available:
                        next_seat = _clockwise_first(
                            available,
                            int(state.get("button_seat") or 0),
                        )["seat_no"]
            else:
                available = [
                    row for row in participants if int(row["stack"]) > 0
                ]
                if available:
                    next_seat = _clockwise_first(
                        available,
                        int(seat["seat_no"]),
                    )["seat_no"]

        state.update(
            {
                "street": street,
                "pot": next_pot,
                "board": board,
                "action_seat": next_seat,
                "action_no": next_action_no,
                "current_bet": current_bet,
                "min_raise": min_raise,
                "contributions": contributions,
                "street_contributions": street_contributions,
                "acted": sorted(acted),
                "folded": sorted(folded),
                "showdown_pending": showdown_pending,
            }
        )

        conn.execute(
            """
            INSERT INTO hand_actions(
                hand_id, table_id, action_no, player_id, seat_no,
                action, amount, state_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hand["hand_id"],
                table_id,
                next_action_no,
                player_id,
                seat["seat_no"],
                action,
                amount,
                json.dumps(state, separators=(",", ":")),
            ),
        )
        if auto_winner is not None:
            payouts = {
                row["player_id"]: (
                    next_pot if row["player_id"] == auto_winner else 0
                )
                for row in seats
            }
            _settle_payouts_in_conn(
                conn,
                table_id,
                {"hand_id": hand["hand_id"], "pot": next_pot},
                payouts,
            )
        else:
            conn.execute(
                """
                UPDATE active_hands
                SET street = ?, pot = ?, action_seat = ?, state_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE table_id = ?
                """,
                (
                    street,
                    next_pot,
                    next_seat,
                    json.dumps(state, separators=(",", ":")),
                    table_id,
                ),
            )

    return get_table_state(table_id)


def submit_player_action_with_session(
    table_id: str,
    session_id: str,
    action: str,
    expected_action_no: int,
    amount: int | None = None,
) -> dict:
    session = get_session(session_id)
    return submit_player_action(
        table_id,
        session["user_id"],
        action,
        expected_action_no,
        amount,
    )


def set_hand_pot(table_id: str, pot: int) -> dict:
    if pot < 0:
        raise ConflictError("pot must be non-negative")
    with transaction() as conn:
        _require_table(conn, table_id)
        hand = conn.execute(
            "SELECT hand_id, state_json FROM active_hands WHERE table_id = ?",
            (table_id,),
        ).fetchone()
        if hand is None:
            raise NotFoundError("no active hand")
        state = json.loads(hand["state_json"])
        state["pot"] = pot
        conn.execute(
            """
            UPDATE active_hands
            SET pot = ?, state_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE table_id = ?
            """,
            (pot, json.dumps(state, separators=(",", ":")), table_id),
        )
    return get_table_state(table_id)


def _settle_payouts_in_conn(
    conn,
    table_id: str,
    hand,
    payouts: dict[str, int],
) -> None:
    seats = conn.execute(
        """
        SELECT player_id, stack
        FROM runtime_seats
        WHERE table_id = ? AND status = 'seated'
        ORDER BY seat_no
        """,
        (table_id,),
    ).fetchall()
    players = {row["player_id"]: int(row["stack"]) for row in seats}

    if any(value < 0 for value in payouts.values()):
        raise ConflictError("payouts must be non-negative")
    unknown = set(payouts) - set(players)
    if unknown:
        raise ConflictError("payout contains unknown player")
    if sum(payouts.values()) != int(hand["pot"]):
        raise ConflictError("payout total must equal pot")

    new_stacks = {
        player_id: stack + int(payouts.get(player_id, 0))
        for player_id, stack in players.items()
    }
    for player_id, stack in new_stacks.items():
        conn.execute(
            """
            UPDATE runtime_seats
            SET stack = ?, updated_at = CURRENT_TIMESTAMP
            WHERE table_id = ? AND player_id = ?
            """,
            (stack, table_id, player_id),
        )

    conn.execute(
        """
        INSERT INTO hand_results(hand_id, table_id, pot, payouts_json, stacks_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            hand["hand_id"],
            table_id,
            int(hand["pot"]),
            json.dumps(payouts, separators=(",", ":")),
            json.dumps(new_stacks, separators=(",", ":")),
        ),
    )
    conn.execute("DELETE FROM active_hands WHERE table_id = ?", (table_id,))
    conn.execute(
        """
        UPDATE runtime_tables
        SET status = 'open', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (table_id,),
    )


def complete_hand(table_id: str, payouts: dict[str, int]) -> dict:
    with transaction() as conn:
        _require_table(conn, table_id)
        hand = conn.execute(
            "SELECT hand_id, pot FROM active_hands WHERE table_id = ?",
            (table_id,),
        ).fetchone()
        if hand is None:
            raise NotFoundError("no active hand")
        _settle_payouts_in_conn(conn, table_id, hand, payouts)
    return get_table_state(table_id)


def calculate_showdown_payouts(table_id: str) -> dict[str, int]:
    conn = connect()
    try:
        _require_table(conn, table_id)
        hand = conn.execute(
            """
            SELECT hand_id, pot, state_json
            FROM active_hands
            WHERE table_id = ?
            """,
            (table_id,),
        ).fetchone()
        if hand is None:
            raise NotFoundError("no active hand")

        state = json.loads(hand["state_json"])
        if not state.get("showdown_pending"):
            raise ConflictError("hand is not ready for showdown")

        pot = int(hand["pot"])
        folded = set(state.get("folded", []))
        board = list(state.get("board", []))
        all_players = list(state.get("players", []))
        participants = [
            player
            for player in all_players
            if player["player_id"] not in folded
        ]
        if not participants:
            raise ConflictError("no eligible showdown players")

        uncontested = state.get("uncontested_winner")
        if uncontested:
            return {
                player["player_id"]: pot if player["player_id"] == uncontested else 0
                for player in all_players
            }

        if len(board) != 5:
            raise ConflictError("showdown requires a complete board")

        scores: dict[str, tuple[int, ...]] = {}
        seat_order: dict[str, int] = {}
        for player in participants:
            row = conn.execute(
                """
                SELECT cards_json
                FROM hand_private_cards
                WHERE hand_id = ? AND player_id = ?
                """,
                (hand["hand_id"], player["player_id"]),
            ).fetchone()
            if row is None:
                raise ConflictError("private cards missing for showdown")
            hole_cards = json.loads(row["cards_json"])
            scores[player["player_id"]] = evaluate_seven(
                [*hole_cards, *board]
            )
            seat_order[player["player_id"]] = int(player["seat_no"])

        contributions = {
            player_id: int(value)
            for player_id, value in dict(
                state.get("contributions", {})
            ).items()
            if int(value) > 0
        }
        if sum(contributions.values()) != pot:
            raise ConflictError("contribution ledger does not match pot")

        payouts = {player["player_id"]: 0 for player in all_players}
        levels = sorted(set(contributions.values()))
        previous = 0
        for level in levels:
            contributors = [
                player_id
                for player_id, amount in contributions.items()
                if amount >= level
            ]
            side_pot = (level - previous) * len(contributors)
            previous = level
            eligible = [
                player_id
                for player_id in contributors
                if player_id not in folded
            ]
            if not eligible:
                continue

            best = max(scores[player_id] for player_id in eligible)
            winners = sorted(
                (
                    player_id
                    for player_id in eligible
                    if scores[player_id] == best
                ),
                key=lambda player_id: seat_order[player_id],
            )
            share, remainder = divmod(side_pot, len(winners))
            for index, winner in enumerate(winners):
                payouts[winner] += share + (1 if index < remainder else 0)

        if sum(payouts.values()) != pot:
            raise ConflictError("side-pot payout calculation mismatch")
        return payouts
    finally:
        conn.close()


def settle_showdown(table_id: str) -> dict:
    payouts = calculate_showdown_payouts(table_id)
    return complete_hand(table_id, payouts)


def set_operator_status(table_id: str, status: str) -> dict:
    if status not in {"paused", "open"}:
        raise ConflictError("unsupported operator status")

    with transaction() as conn:
        _require_table(conn, table_id)
        active = conn.execute(
            "SELECT 1 FROM active_hands WHERE table_id = ?", (table_id,)
        ).fetchone()
        resolved = "playing" if status == "open" and active else status
        conn.execute(
            """
            UPDATE runtime_tables
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (resolved, table_id),
        )
    return get_table_state(table_id)


def append_table_event(table_id: str, event_type: str, payload: dict) -> dict:
    with transaction() as conn:
        _require_table(conn, table_id)
        cur = conn.execute(
            """
            INSERT INTO realtime_events(table_id, event_type, payload_json)
            VALUES (?, ?, ?)
            """,
            (table_id, event_type, json.dumps(payload, separators=(",", ":"))),
        )
        seq = int(cur.lastrowid)
        row = conn.execute(
            """
            SELECT seq, table_id, event_type, payload_json, created_at
            FROM realtime_events
            WHERE seq = ?
            """,
            (seq,),
        ).fetchone()
    return {
        "seq": row["seq"],
        "table_id": row["table_id"],
        "event_type": row["event_type"],
        "payload": json.loads(row["payload_json"]),
        "created_at": row["created_at"],
    }


def list_table_events_since(table_id: str, after_seq: int, limit: int = 100) -> list[dict]:
    conn = connect()
    try:
        _require_table(conn, table_id)
        rows = conn.execute(
            """
            SELECT seq, table_id, event_type, payload_json, created_at
            FROM realtime_events
            WHERE table_id = ? AND seq > ?
            ORDER BY seq ASC
            LIMIT ?
            """,
            (table_id, after_seq, max(1, min(limit, 500))),
        ).fetchall()
        return [
            {
                "seq": row["seq"],
                "table_id": row["table_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def latest_table_seq(table_id: str) -> int:
    conn = connect()
    try:
        _require_table(conn, table_id)
        row = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) AS seq FROM realtime_events WHERE table_id = ?",
            (table_id,),
        ).fetchone()
        return int(row["seq"])
    finally:
        conn.close()


def operator_abort_hand(table_id: str, reason: str) -> dict:
    reason = reason.strip()
    if not reason:
        raise ConflictError("recovery reason is required")

    with transaction() as conn:
        _require_table(conn, table_id)
        table = conn.execute(
            "SELECT status FROM runtime_tables WHERE id = ?", (table_id,)
        ).fetchone()
        if table["status"] != "paused":
            raise ConflictError("table must be paused before recovery")

        hand = conn.execute(
            "SELECT hand_id, state_json FROM active_hands WHERE table_id = ?",
            (table_id,),
        ).fetchone()
        if hand is None:
            raise NotFoundError("no active hand")

        hand_state = json.loads(hand["state_json"])
        conn.execute(
            """
            INSERT INTO recovery_actions(
                table_id, hand_id, action, reason, details_json
            ) VALUES (?, ?, 'abort_hand', ?, ?)
            """,
            (
                table_id,
                hand["hand_id"],
                reason,
                json.dumps({"hand_state": hand_state}, separators=(",", ":")),
            ),
        )
        conn.execute("DELETE FROM active_hands WHERE table_id = ?", (table_id,))
        conn.execute(
            """
            UPDATE runtime_tables
            SET status = 'open', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (table_id,),
        )
    return get_table_state(table_id)


def list_recovery_actions(table_id: str, limit: int = 100) -> list[dict]:
    conn = connect()
    try:
        _require_table(conn, table_id)
        rows = conn.execute(
            """
            SELECT id, table_id, hand_id, action, reason, details_json, created_at
            FROM recovery_actions
            WHERE table_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (table_id, max(1, min(limit, 500))),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "table_id": row["table_id"],
                "hand_id": row["hand_id"],
                "action": row["action"],
                "reason": row["reason"],
                "details": json.loads(row["details_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def create_session(
    user_id: str,
    provider: str,
    data: dict | None = None,
    expires_at: str | None = None,
) -> dict:
    session_id = str(uuid.uuid4())
    payload = data or {}
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO auth_sessions(session_id, user_id, provider, data_json, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user_id,
                provider,
                json.dumps(payload, separators=(",", ":")),
                expires_at,
            ),
        )
    return get_session(session_id)


def get_session(session_id: str) -> dict:
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT session_id, user_id, provider, data_json, expires_at, updated_at
            FROM auth_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("session not found")
        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "provider": row["provider"],
            "data": json.loads(row["data_json"]),
            "expires_at": row["expires_at"],
            "updated_at": row["updated_at"],
        }
    finally:
        conn.close()


def join_table_with_session(
    table_id: str,
    session_id: str,
    seat_no: int,
    stack: int,
) -> dict:
    session = get_session(session_id)
    return join_table(table_id, session["user_id"], seat_no, stack)


def get_player_table_view(table_id: str, session_id: str) -> dict:
    session = get_session(session_id)
    state = get_table_state(table_id)
    view = {
        "table": state,
        "player_id": session["user_id"],
        "hole_cards": [],
    }

    hand = state.get("active_hand")
    if hand is None:
        return view

    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT cards_json
            FROM hand_private_cards
            WHERE hand_id = ? AND table_id = ? AND player_id = ?
            """,
            (hand["hand_id"], table_id, session["user_id"]),
        ).fetchone()
        if row is not None:
            view["hole_cards"] = json.loads(row["cards_json"])
        return view
    finally:
        conn.close()


def delete_session(session_id: str) -> None:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM auth_sessions WHERE session_id = ?", (session_id,)
        )
        if cur.rowcount == 0:
            raise NotFoundError("session not found")


def list_hand_history(table_id: str, limit: int = 50) -> list[dict]:
    conn = connect()
    try:
        _require_table(conn, table_id)
        rows = conn.execute(
            """
            SELECT hand_id, pot, payouts_json, stacks_json, completed_at
            FROM hand_results
            WHERE table_id = ?
            ORDER BY completed_at DESC, hand_id DESC
            LIMIT ?
            """,
            (table_id, max(1, min(limit, 200))),
        ).fetchall()
        return [
            {
                "hand_id": row["hand_id"],
                "pot": row["pot"],
                "payouts": json.loads(row["payouts_json"]),
                "final_stacks": json.loads(row["stacks_json"]),
                "completed_at": row["completed_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def list_hand_actions(table_id: str, hand_id: str) -> list[dict]:
    conn = connect()
    try:
        _require_table(conn, table_id)
        rows = conn.execute(
            """
            SELECT action_no, player_id, seat_no, action, amount,
                   state_json, created_at
            FROM hand_actions
            WHERE table_id = ? AND hand_id = ?
            ORDER BY action_no ASC
            """,
            (table_id, hand_id),
        ).fetchall()
        return [
            {
                "action_no": row["action_no"],
                "player_id": row["player_id"],
                "seat_no": row["seat_no"],
                "action": row["action"],
                "amount": row["amount"],
                "state": json.loads(row["state_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


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
