# INARENA checkpoint

## Source of truth
GitHub repository `pokeratlas/inarena-` is the primary codebase.
The project follows the INARENA Product Engineering Standard.

## Product / architecture specifications
Formal repository specifications now exist for:
- Product Map
- Platform Architecture
- Engineering Quality Gates
- Poker Runtime State Machine
- Ledger Invariants
- Tournament Lifecycle
- Cash Waitlist + Seat Reservation + Idempotency

## Verified backend
Implemented and verified in GitHub Actions through schema v11:

### Poker Runtime
- server-authoritative NL Hold'em runtime
- blinds / button / action order
- min-raise / short all-in handling
- main and side pots
- showdown / tie split
- timeout policy
- realtime reconnect / replay
- authenticated private cards
- hand history

### Tournament
- scheduled / registering / running / finished / cancelled lifecycle
- registration / withdrawal
- late registration cutoff
- rebuy / add-on windows
- per-player rebuy limit
- one-time add-on
- elimination / finish place / winner
- blind schedules

### Cash / Ledger
- internal non-monetary chip balances
- cash buy-in min/max
- atomic production balance debit on buy-in
- atomic cash-out credit
- persistent table ledger
- operator balance adjustment / audit

### Waitlist / Reservation
- persistent FIFO cash waitlist
- one active waitlist entry per table/player
- server-side seat reservation
- configurable reservation TTL
- automatic expiry
- expired reservation yields to the next waiting player
- reservation claim uses normal buy-in validation
- direct join cannot bypass another player's reservation
- freed cash seats immediately trigger assignment
- waitlist count exposed in table state

### Idempotency
Authenticated player mutations accept persistent idempotency keys:
- join
- stand
- player action
- tournament register / unregister
- rebuy
- add-on
- waitlist join / leave
- reservation claim

Verified:
- repeated successful request returns persisted original response
- same key + different request fingerprint is rejected
- duplicate buy-in does not duplicate ledger movement
- duplicate player action does not create second hand action
- duplicate add-on does not add chips twice
- duplicate waitlist mutation does not duplicate queue entry
- idempotency records survive application restart

## Verified frontend
- Concept 2 mobile shell
- Telegram session restore / refresh
- ONLINE lobby / live table
- cash/tournament separation
- internal chip balance
- tournament registration lifecycle UI
- cash waitlist count
- queue position
- leave-waitlist control
- reserved seat claim
- direct cash join hidden when an active queue/reservation exists
- client mutation functions generate Idempotency-Key and can accept an explicit key for retry
- operator dashboard / audit / blind controls / tournament controls

## CI
Latest backend CI: PASS.
Latest frontend CI: PASS.
Schema v11: PASS.
Waitlist FIFO: PASS.
Reservation expiry/reassignment: PASS.
Reservation claim: PASS.
Reserved-seat bypass prevention: PASS.
Persistent idempotency replay after restart: PASS.
Existing NLH / ledger / security / tournament regression suite: PASS.

## Production hardening still required
Current idempotency records are persisted after a successful business mutation in a separate transaction.
A process crash in the narrow interval between the business commit and idempotency-record commit could allow a retry to execute twice.

Before public production release:
- business mutation + idempotency result must become one atomic transaction, or
- use a transactional outbox / command journal pattern.

## Current deployment blocker
The connected Vercel integration currently exposes no accessible Vercel team/account, so public preview deployment remains blocked.

## Next bounded features

### 1. Transactional command / idempotency hardening
- atomic command journal
- remove post-commit crash window
- transactional realtime outbox

### 2. Operator exports and reports
- table ledger export
- tournament result export
- registration export
- audit export
- CSV / JSON report endpoints

### 3. Production data layer
- PostgreSQL migration plan
- Redis coordination/realtime plan
- connection pooling
- migration tooling
- backup / restore
- staging environment

### 4. Deployment readiness
- Docker runtime
- environment contract
- health/readiness endpoints
- observability
- persistent backend hosting
- preview / staging deployment
