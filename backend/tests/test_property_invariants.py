from __future__ import annotations

import importlib
import os
import tempfile
from itertools import combinations

from fastapi.testclient import TestClient
from hypothesis import given, settings, strategies as st

from app.poker import evaluate_five, evaluate_seven


RANKS = "23456789TJQKA"
SUITS = "cdhs"
DECK = [f"{rank}{suit}" for rank in RANKS for suit in SUITS]


@st.composite
def unique_cards(draw, count: int):
    return draw(
        st.lists(
            st.sampled_from(DECK),
            min_size=count,
            max_size=count,
            unique=True,
        )
    )


@given(unique_cards(5))
@settings(max_examples=300, deadline=None)
def test_five_card_evaluation_is_order_invariant(cards):
    score = evaluate_five(tuple(cards))
    rotated = cards[1:] + cards[:1]
    reversed_cards = list(reversed(cards))

    assert evaluate_five(tuple(rotated)) == score
    assert evaluate_five(tuple(reversed_cards)) == score
    assert 0 <= score[0] <= 8


@given(unique_cards(7))
@settings(max_examples=300, deadline=None)
def test_seven_card_score_is_best_of_all_five_card_subsets(cards):
    score = evaluate_seven(cards)
    subset_scores = [
        evaluate_five(combo)
        for combo in combinations(cards, 5)
    ]

    assert score == max(subset_scores)
    assert all(score >= subset for subset in subset_scores)


@given(
    stack_a=st.integers(min_value=1_000, max_value=100_000),
    stack_b=st.integers(min_value=1_000, max_value=100_000),
)
@settings(max_examples=20, deadline=None)
def test_heads_up_immediate_fold_conserves_total_chips(
    stack_a,
    stack_b,
):
    with tempfile.TemporaryDirectory() as directory:
        os.environ["INARENA_DB_PATH"] = os.path.join(
            directory,
            "chips.sqlite3",
        )
        os.environ["INARENA_OPERATOR_KEY"] = "operator"
        os.environ["INARENA_ENABLE_LEGACY_API"] = "1"
        os.environ["INARENA_ENV"] = "test"

        import app.db as db
        import app.service as service
        import app.main as main

        importlib.reload(db)
        importlib.reload(service)
        importlib.reload(main)

        with TestClient(main.app) as client:
            table = client.post(
                "/api/v1/tables",
                json={"name": "Property"},
            ).json()
            table_id = table["id"]

            for player_id, seat_no, stack in (
                ("p1", 1, stack_a),
                ("p2", 2, stack_b),
            ):
                joined = client.post(
                    f"/api/v1/tables/{table_id}/join",
                    json={
                        "player_id": player_id,
                        "seat_no": seat_no,
                        "stack": stack,
                    },
                )
                assert joined.status_code == 200

            started = client.post(
                f"/api/v1/tables/{table_id}/start-hand",
                json={"button_seat": 1},
            )
            assert started.status_code == 200
            state = started.json()
            action_seat = state["active_hand"]["action_seat"]
            actor = next(
                seat["player_id"]
                for seat in state["seats"]
                if seat["seat_no"] == action_seat
            )

            folded = client.post(
                f"/api/v1/tables/{table_id}/action",
                json={
                    "player_id": actor,
                    "action": "fold",
                    "expected_action_no": 0,
                },
            )
            assert folded.status_code == 200
            final_state = folded.json()

            assert final_state["active_hand"] is None
            assert sum(
                seat["stack"] for seat in final_state["seats"]
            ) == stack_a + stack_b

