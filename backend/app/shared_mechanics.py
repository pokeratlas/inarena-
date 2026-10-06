"""Consumer-owned SQL/replay adapter. Core has no persistence dependency.

Rebuild from persisted initial public state, private-card rows and ordered
action records, using only the public shared mechanics interface.
"""
import json
from contracts.hand import HandConfig, Action
from poker_core import create_hand, apply_action, advance_street, legal_actions, settle_hand

from poker_core.api import API_VERSION
CORE_VERSION = '0.2.2-candidate'
if API_VERSION != CORE_VERSION:
    raise RuntimeError('Consumer requires pinned Shared Core 0.2.2')

def rebuild(conn, hand_id, state):
    players = sorted(state['players'], key=lambda p: int(p['seat_no']))
    ids = tuple(p['player_id'] for p in players)
    physical = tuple(int(p['seat_no']) for p in players)
    if state.get('mechanics_version') != CORE_VERSION:
        raise ValueError('unsupported consumer mechanics version')
    initial = state.get('shared_initial_stacks')
    if initial is None:
        raise ValueError('legacy hand has no shared initial stack contract')
    config = HandConfig(tuple(initial), int(state['small_blind']), int(state['big_blind']),
                        physical.index(int(state['button_seat'])), 0,
                        allow_free_fold=True, odd_chip_policy='ascending_seat')
    holes = {ids.index(row['player_id']): tuple(json.loads(row['cards_json']))
             for row in conn.execute('SELECT player_id, cards_json FROM hand_private_cards WHERE hand_id = ?', (hand_id,)).fetchall()}
    hand = create_hand(config, imported=True, known_holes=holes)
    records = conn.execute('SELECT action_no, player_id, action, amount, state_json FROM hand_actions WHERE hand_id = ? ORDER BY action_no', (hand_id,)).fetchall()
    if len(records) != int(state['action_no']) or any(int(r['action_no']) != i+1 for i,r in enumerate(records)):
        raise ValueError('persisted action sequence is not contiguous')
    for record in records:
        kind = record['action']
        hand = apply_action(hand, Action(ids.index(record['player_id']), kind,
                                        int(record['amount']) if kind in ('bet','raise') else None))
        target = json.loads(record['state_json'])
        board = target['board']
        while hand.street != target['street']:
            count = 3 if hand.street == 'preflop' else 1
            hand = advance_street(hand, cards=tuple(board[len(hand.board):len(hand.board)+count]))
    if (hand.street != state['street'] or list(hand.board) != state['board'] or
        hand.pot_units != int(state['pot']) or
        any(p.contribution_units != int(state['contributions'].get(ids[i], 0)) for i,p in enumerate(hand.players))):
        raise ValueError('persisted state does not match public action replay')
    rows = conn.execute('SELECT player_id,stack FROM runtime_seats WHERE table_id = (SELECT table_id FROM active_hands WHERE hand_id = ?)', (hand_id,)).fetchall()
    balances = {r['player_id']:int(r['stack']) for r in rows}
    if any(balances.get(ids[i]) != p.stack_units for i,p in enumerate(hand.players)):
        raise ValueError('persisted stacks do not match action replay')
    expected_actor = None if hand.actor is None else physical[hand.actor]
    if expected_actor != state['action_seat']:
        raise ValueError('persisted actor does not match action replay')
    return hand, ids, physical

def prepare_action(conn, hand_id, state, player_id, kind, amount):
    hand, ids, physical = rebuild(conn, hand_id, state)
    seat = ids.index(player_id)
    if kind not in legal_actions(hand, seat):
        raise ValueError('shared rules reject action')
    candidate = apply_action(hand, Action(seat, kind, amount if kind in ('bet','raise') else None))
    return hand, candidate, ids, physical

def payouts(conn, hand_id, state):
    hand, ids, _ = rebuild(conn, hand_id, state)
    settled = settle_hand(hand)
    return {player: settled.payouts_units[i] + settled.returned_units[i] for i, player in enumerate(ids)}
