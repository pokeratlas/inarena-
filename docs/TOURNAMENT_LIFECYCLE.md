# Tournament Lifecycle

## Status state machine
`scheduled -> registering -> running -> finished`
`scheduled -> cancelled`
`registering -> cancelled`

Finished and cancelled are terminal.

## Time fields
- `scheduled_start_at`
- `registration_open_at`
- `registration_close_at`
- `late_registration_close_at`

All persisted timestamps are UTC epoch seconds.

## Registration
A player may register when:
- table mode is `tournament`;
- tournament status is `registering`; or
- tournament status is `running` and late registration is still open.

A registration is unique per tournament/player.

## Seating
Registration and seating are separate concepts.

Before the tournament starts:
- registered players may exist without a seat.

At start:
- registered players are eligible to be seated.

During late registration:
- a newly registered player may be seated with the configured starting stack if a seat is available.

## Start
Operator start requires:
- tournament status `registering`;
- at least two registered/eligible players;
- registration open time reached, if configured.

Starting transitions status to `running`.

## Registration close
Normal registration closes at `registration_close_at`.
Late registration may continue until `late_registration_close_at`.

After late registration cutoff:
- no new registration is accepted;
- rebuy/add-on policy remains governed by its own windows.

## Finish
When:
- rebuy window is closed; and
- exactly one active player with chips remains,

the tournament transitions to `finished`, stores winner and finish time.

## Cancel
Operator may cancel only from `scheduled` or `registering`.
No new hands may start after cancellation.
