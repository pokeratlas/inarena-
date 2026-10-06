from __future__ import annotations

from collections import Counter
from itertools import combinations


RANK_VALUE = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}


def _straight_high(values: list[int]) -> int | None:
    unique = sorted(set(values), reverse=True)
    if 14 in unique:
        unique.append(1)
    for index in range(len(unique) - 4):
        window = unique[index : index + 5]
        if window[0] - window[4] == 4:
            return window[0]
    return None


def evaluate_five(cards: tuple[str, ...]) -> tuple[int, ...]:
    values = sorted((RANK_VALUE[card[0]] for card in cards), reverse=True)
    suits = [card[1] for card in cards]
    counts = Counter(values)
    groups = sorted(
        ((count, value) for value, count in counts.items()),
        reverse=True,
    )
    flush = len(set(suits)) == 1
    straight_high = _straight_high(values)

    if flush and straight_high is not None:
        return (8, straight_high)

    quads = [value for value, count in counts.items() if count == 4]
    if quads:
        quad = max(quads)
        kicker = max(value for value in values if value != quad)
        return (7, quad, kicker)

    trips = sorted(
        (value for value, count in counts.items() if count == 3),
        reverse=True,
    )
    pairs = sorted(
        (value for value, count in counts.items() if count >= 2),
        reverse=True,
    )
    if trips:
        trip = trips[0]
        pair_candidates = [value for value in pairs if value != trip]
        if pair_candidates:
            return (6, trip, pair_candidates[0])

    if flush:
        return (5, *values)

    if straight_high is not None:
        return (4, straight_high)

    if trips:
        trip = trips[0]
        kickers = [value for value in values if value != trip][:2]
        return (3, trip, *kickers)

    exact_pairs = sorted(
        (value for value, count in counts.items() if count == 2),
        reverse=True,
    )
    if len(exact_pairs) >= 2:
        high_pair, low_pair = exact_pairs[:2]
        kicker = max(
            value
            for value in values
            if value not in {high_pair, low_pair}
        )
        return (2, high_pair, low_pair, kicker)

    if len(exact_pairs) == 1:
        pair = exact_pairs[0]
        kickers = [value for value in values if value != pair][:3]
        return (1, pair, *kickers)

    return (0, *values)


def evaluate_seven(cards: list[str]) -> tuple[int, ...]:
    if len(cards) != 7:
        raise ValueError("seven cards are required")
    return max(evaluate_five(combo) for combo in combinations(cards, 5))
