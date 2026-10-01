# Poker Runtime State Machine

## Table states
`open -> playing -> open`
`open -> paused -> open`
`open -> closed`

Closed is terminal for new joins and new hands.

## Hand lifecycle
`idle -> preflop -> flop -> turn -> river -> settlement -> idle`

A hand may terminate early through uncontested settlement.

## Player action contract
A player mutation is valid only when all conditions hold:
- authenticated identity resolves to the seated player;
- table is in `playing`;
- hand exists;
- player owns `action_seat`;
- `expected_action_no` equals authoritative `action_no`;
- action is legal for the current betting state;
- chip movement is valid against current stack.

## Betting round completion
A betting round completes when every actionable player:
- has acted since the last full raise; and
- has matched `current_bet`, or is all-in.

A full raise resets the acted set to the aggressor.
A short all-in may increase `current_bet` but does not reset the full-raise obligation.

## Timeout
At `action_deadline_epoch`:
- CHECK when the player faces no outstanding bet;
- otherwise FOLD.

Timeout resolution uses the same authoritative action path as normal player actions.

## Settlement invariants
- payout total equals pot;
- contribution tiers determine main/side pots;
- only eligible non-folded players may win a pot;
- settled hands are immutable and never become active again;
- public state never contains private hole cards.

## Reconnect
A reconnecting client receives a snapshot and event replay cursor.
Stale or duplicate player actions are rejected by sequence validation.
