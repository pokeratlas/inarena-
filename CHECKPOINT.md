# INARENA checkpoint

## Source of truth
GitHub repository `pokeratlas/inarena-` is the primary codebase.
The project is cloud-first and follows the INARENA Engineering Standard.

## Product structure
- INARENA Player
- INARENA Online
- INARENA Clubs
- INARENA Operator
- Shared Platform Core

## Architecture / standards
Formal specifications now exist for:
- Product Map
- Platform Architecture
- Engineering Quality Gates
- Poker Runtime State Machine
- Ledger Invariants
- Tournament Lifecycle

## Verified backend
Implemented and verified in GitHub Actions:
- schema migrations through v10
- explicit tournament lifecycle:
  - scheduled
  - registering
  - running
  - finished
  - cancelled
- lifecycle timing fields:
  - scheduled_start_at
  - registration_open_at
  - registration_close_at
  - late_registration_close_at
- authenticated tournament registration
- registration withdrawal before tournament start
- late registration while tournament is running
- late-registration cutoff enforcement
- operator lifecycle commands:
  - open-registration
  - start
  - cancel
- minimum two registered/eligible players before start
- production tournament hand start requires lifecycle status running
- production tournament seating composes registration validation
- registration count exposed in public table state
- tournament winner settlement transitions lifecycle to finished

Previously verified platform capabilities remain:
- NL Hold'em server-authoritative runtime
- blinds/button/action sequencing/min-raise/side pots/showdown
- realtime reconnect/replay and timeout policy
- Telegram auth and sessions
- internal non-monetary chip balances and ledger
- cash/tournament table policies
- rebuy/add-on windows
- tournament finish places
- operator audit/dashboard/recovery
- production API hardening

## Verified frontend
- tournament lifecycle status displayed in ONLINE lobby
- registration count displayed
- authenticated Register / Withdraw controls
- tournament seat button only appears for registered players after status becomes running
- cash flow remains separate
- operator dashboard exposes Open registration / Start tournament / Cancel
- existing blind schedule, rebuy/add-on, close-table and audit controls remain

## CI
Latest backend CI: PASS.
Latest frontend CI: PASS.
Tournament lifecycle tests: PASS.
Late-registration cutoff tests: PASS.
Registration withdrawal tests: PASS.
Existing NLH / ledger / security / reconnect regression suite: PASS.

## Current external blocker
The connected Vercel integration currently returns no accessible Vercel team/account, so public preview deployment remains blocked.

## Next bounded feature
### Cash Waitlist + Seat Reservation + Idempotency

Acceptance criteria:
1. Cash-table waitlist is ordered and persistent.
2. A freed seat may be reserved for the next eligible player.
3. Seat reservation has a server-side expiry timestamp.
4. Expired reservation can be reclaimed automatically.
5. Join, stand, registration, rebuy, add-on and player action mutations accept idempotency keys.
6. Replaying the same mutation with the same idempotency key returns the original result without double chip movement.
7. Idempotency state survives process restart.
8. New rules are covered by unit/integration tests before UI work.
