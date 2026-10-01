# Cash Waitlist + Seat Reservation + Idempotency

## Scope
Applies to cash tables only.

## Waitlist
- Persistent ordered queue per table.
- One active waitlist entry per table/player.
- Player may join/leave waitlist while not seated.
- Queue order is FIFO by creation time / id.
- Closed tables do not accept new waitlist entries.

## Seat reservation
When a seat becomes free:
1. Find the first active waitlist player.
2. Create a reservation for that player and seat.
3. Reservation has a server-side expiry timestamp.
4. Only the reserved player may claim the reserved seat before expiry.
5. Expired reservations may be reclaimed automatically.
6. A player may have at most one active reservation per table.
7. A seat may have at most one active reservation.

## Reservation timeout
Default TTL is configurable with `INARENA_SEAT_RESERVATION_SECONDS`.
Expired reservations are marked expired and the next waitlist player may receive the seat.

## Idempotency
Player mutation endpoints accept `Idempotency-Key`.

Initial required mutations:
- authenticated cash/table join
- authenticated stand
- tournament register / unregister
- rebuy
- add-on
- player action
- waitlist join / leave
- reservation claim

## Idempotency behavior
For the same authenticated user + operation scope + idempotency key:
- first request executes normally;
- response is persisted;
- repeated request returns the persisted response;
- chip movement is not repeated;
- action sequence is not repeated;
- result survives process restart.

A reused key with a different request fingerprint is rejected.

## Storage
Idempotency records persist:
- user_id
- operation
- idempotency_key
- request_fingerprint
- response_json
- status_code
- created_at

## Safety invariants
- No waitlist operation changes chip balances.
- Reserving a seat does not debit player balance.
- Claiming a reservation performs the normal atomic cash buy-in.
- A reservation cannot bypass cash buy-in min/max or available balance checks.
- Replayed idempotent mutations cannot duplicate ledger entries.
