# INARENA checkpoint

## Source of truth
GitHub repository `pokeratlas/inarena-` is the primary codebase.
The project follows the INARENA Product Engineering Standard.

## Product / architecture specifications
Formal repository specifications exist for:
- Product Map
- Platform Architecture
- Engineering Quality Gates
- Poker Runtime State Machine
- Ledger Invariants
- Tournament Lifecycle
- Cash Waitlist + Seat Reservation + Idempotency

## Verified backend
Implemented and verified in GitHub Actions through schema v13.

### Tournament lifecycle
- scheduled / registering / running / finished / cancelled
- registration / withdrawal
- late registration cutoff
- registration count
- operator open-registration / start / cancel
- production hand start requires running status

### Cash waitlist / reservations
- persistent FIFO waitlist
- server-side seat reservations
- configurable reservation TTL
- automatic expiry and reassignment
- reservation claim
- direct join cannot bypass reservation
- freed seat immediately triggers assignment

### Durable idempotency command journal
- authenticated player mutations accept Idempotency-Key
- command is reserved as in_progress before business execution
- completed commands replay the persisted response
- same key with different request fingerprint is rejected
- in_progress/pending commands block duplicate execution
- journal survives process restart
- duplicate buy-in/action/add-on/waitlist mutations are regression tested

### Transactional realtime outbox
- schema-backed realtime_outbox
- state snapshot is captured from the same DB transaction
- dispatcher atomically appends to realtime_events
- outbox_id unique index prevents duplicate event-log delivery
- failed/rolled-back mutations do not create extra outbox records
- outbox-first WebSocket broadcaster with fallback for paths not migrated yet
- migrated paths include:
  - join
  - stand
  - start hand
  - production authenticated cash join/stand
  - waitlist join/leave
  - reservation claim

### Existing verified platform
- server-authoritative NL Hold'em runtime
- blinds / button / min raise / all-in / side pots / showdown
- timeout and reconnect/replay
- private cards
- cash/tournament policies
- internal non-monetary chip balances and ledger
- rebuy/add-on controls
- finish places / winner
- operator dashboard / audit / recovery
- Telegram auth and session lifecycle

## Verified frontend
- Concept 2 mobile shell
- tournament lifecycle and registration UX
- internal chip balance
- cash waitlist count / position
- reserved-seat claim
- waitlist leave/join controls
- client-generated Idempotency-Key with explicit-key retry support
- operator dashboard and existing tournament/cash controls

## CI
Latest backend CI: PASS.
Latest frontend CI: PASS.
Schema v13: PASS.
Waitlist/reservation suite: PASS.
Durable idempotency suite: PASS.
Restart replay suite: PASS.
Pending-command duplicate block: PASS.
Transactional realtime outbox suite: PASS.
Existing NLH / ledger / security / tournament suite: PASS.

## Realtime consistency
Verified:
- player betting mutation, automatic showdown settlement and final realtime outbox snapshot now share one database transaction;
- uncontested settlement emits a final hand_completed snapshot;
- river showdown emits a final hand_completed snapshot;
- non-terminal actions emit player_action;
- no stale pre-settlement snapshot is published from the action path;
- SQLite regression suite: PASS;
- PostgreSQL integration: PASS.

## Current deployment blocker
The connected Vercel integration currently exposes no accessible Vercel team/account.

## Next bounded features

### Operator exports / reports
- table ledger
- tournament results
- tournament registrations
- operator audit
- JSON + CSV

### Production data layer
- PostgreSQL migration
- Redis coordination
- migration tooling
- backups / restore
- staging

### Deployment readiness
- Docker
- environment contract
- readiness checks
- observability
- persistent backend hosting


## Operator Reports quality gate
Verified:
- operator-authenticated JSON exports
- stable UTF-8 CSV exports
- table ledger report
- tournament results report
- tournament registrations report
- operator audit report
- deterministic row ordering
- compact JSON serialization for nested details
- invalid export formats return 400

Latest operator-report backend CI: PASS.
Latest frontend CI: PASS.


## Production runtime milestone
Verified:
- operator JSON/CSV report contracts
- backend production Docker image
- writable persistent container data path for the current SQLite baseline
- /health liveness endpoint
- /ready readiness endpoint
- production environment validation
- production readiness rejects legacy API mode
- Docker image build is now a backend CI gate

Latest backend CI including Docker build: PASS.
Latest frontend CI: PASS.

## PostgreSQL migration status
Production data-layer architecture is specified in:
- docs/PRODUCTION_DATA_LAYER.md
- docs/RUNTIME_ENVIRONMENT.md

Verified:
- runtime database adapter supports SQLite and PostgreSQL;
- PostgreSQL schema parity integration is live;
- PostgreSQL integration CI: PASS;
- production readiness endpoint works against PostgreSQL;
- bounded PostgreSQL connection pool is implemented;
- pool min/max/acquisition timeout are environment-configurable;
- FastAPI startup/shutdown manages pool lifecycle.

SQLite remains the fast local-development baseline.
PostgreSQL is the production target.


## Next production bounded feature
### Redis multi-instance realtime coordination
Acceptance criteria:
1. PostgreSQL remains the authoritative state/event source.
2. Redis is used only for cross-instance event fan-out and ephemeral coordination.
3. A realtime event committed to PostgreSQL may be published to Redis after outbox dispatch.
4. Each backend instance subscribes and forwards remote events to its local WebSocket clients.
5. The originating instance must not double-deliver its own event.
6. Redis outage must not corrupt poker/ledger state.
7. Single-instance mode continues to work without Redis.
8. Redis connectivity/coordination status is surfaced in readiness diagnostics.
