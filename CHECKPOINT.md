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


## PostgreSQL pool milestone
Verified:
- bounded PostgreSQL connection pool;
- configurable min/max/acquisition timeout;
- application startup opens and validates the pool;
- application shutdown closes the pool;
- readiness reports database backend and pool diagnostics;
- PostgreSQL pool integration CI: PASS.

## Redis realtime coordination milestone
Verified:
- Redis remains non-authoritative;
- PostgreSQL/outbox remains the realtime source of truth;
- optional Redis pub/sub fans committed events across backend instances;
- source instance IDs prevent self-duplicate delivery;
- remote backend instances forward events only to their local WebSocket clients;
- single-instance/no-Redis mode remains functional;
- Redis diagnostics are exposed through readiness;
- two-instance Redis integration test: PASS;
- Redis outage cannot roll back or mutate committed poker/ledger state.

## Next reliability bounded feature
### Crash-safe idempotency completion
Current durable command reservation prevents concurrent duplicate execution, but a process crash after business commit and before command completion can leave an idempotency key in `in_progress`.

Target:
1. Couple idempotency completion to the same transaction as critical business mutations where practical.
2. For unavoidable split flows, persist an authoritative mutation/result reference that can reconcile an interrupted command.
3. Never blindly re-execute a chip-moving command whose prior outcome is unknown.
4. Add restart/crash regression tests for buy-in, cash-out, reservation claim and player action.


## Crash-safe idempotency milestone
Verified through schema v14:
- critical business mutations write a mutation receipt in the same database transaction as the authoritative state change;
- receipt contains the request fingerprint and final response snapshot;
- if the process crashes after business commit but before idempotency journal completion, retry recovers the committed response from the receipt;
- retry does not repeat chip movement, ledger insertion or hand action;
- recovered journal is promoted from in_progress to completed;
- same-key / different-payload protection remains enforced.

Crash simulation coverage:
- production cash buy-in: PASS;
- production cash-out: PASS;
- reservation claim: PASS;
- player action: PASS.

PostgreSQL:
- schema v14 parity: PASS;
- prior metadata version upgrade 13 -> 14: PASS.

## Current production readiness direction
The main correctness layers are now in place:
- server-authoritative poker state;
- transactional settlement/outbox;
- durable idempotency plus crash receipts;
- PostgreSQL adapter and bounded pool;
- Redis multi-instance realtime fan-out;
- production container build;
- readiness diagnostics.

## Next bounded feature
### Production migrations + staging/deploy gate
Acceptance criteria:
1. Replace ad-hoc PostgreSQL version bumping with an explicit ordered migration runner.
2. Preserve upgrade path from the current schema without destructive resets.
3. Add staging environment contract using PostgreSQL + Redis.
4. Add migration-before-start deployment command.
5. Add backup/restore runbook.
6. Add smoke-test gate covering ready/auth/table lifecycle/realtime.
7. Keep local SQLite fast-test workflow unchanged.


## Production migrations + staging/deploy milestone
Verified:
- explicit ordered PostgreSQL migration runner;
- migration CLI supports upgrade / status / check;
- production container runs migrations before starting Uvicorn;
- staging stack uses PostgreSQL + Redis;
- staging environment template is committed without secrets;
- staging smoke test verifies:
  - /health;
  - /ready;
  - auth boundary;
  - operator authentication;
  - table creation/close lifecycle;
  - WebSocket snapshot;
- backup/restore runbook is documented;
- deployment/rollback runbook is documented;
- backend CI staging-smoke gate: PASS;
- PostgreSQL integration: PASS;
- Redis integration: PASS;
- frontend CI: PASS.

## Next bounded feature
### Observability + release diagnostics
Acceptance criteria:
1. Structured request logs include request ID, method, path, status and duration.
2. Request ID is returned to clients and propagated through error responses.
3. Runtime diagnostics expose database backend/pool, Redis coordination and schema version.
4. Realtime diagnostics expose local WebSocket connection count and outbox backlog.
5. Sensitive secrets, session IDs and private cards never appear in logs.
6. Production log level is environment-configurable.
7. A release metadata endpoint exposes commit/release identifier without secrets.
8. CI covers request-ID propagation and diagnostics contracts.


## Observability + release diagnostics milestone
Verified:
- structured JSON request logs;
- request ID generation/validation and response propagation;
- request ID included in controlled error responses;
- logs exclude request bodies and sensitive authentication headers;
- environment-configurable log level;
- public release metadata endpoint;
- operator-only runtime diagnostics;
- diagnostics include:
  - release/environment;
  - database backend/schema/pool;
  - Redis coordination;
  - local WebSocket connection count;
  - realtime outbox backlog;
- SQLite observability regression suite: PASS;
- PostgreSQL integration: PASS;
- Redis integration: PASS;
- staging smoke: PASS;
- frontend CI: PASS.

## Next bounded feature
### Production security perimeter
Acceptance criteria:
1. Explicit CORS allowlist; production must not default to wildcard origins.
2. Standard security headers on HTTP responses.
3. Configurable request body size ceiling for JSON mutation endpoints.
4. Per-IP / per-session rate limiting for auth and player mutation endpoints.
5. WebSocket origin validation and connection-rate protection.
6. Operator endpoints have stricter rate limits than public reads.
7. Rate-limit storage may use Redis but failure must not corrupt game state.
8. Security controls have regression tests and staging smoke coverage.


## Production security perimeter + scoped operator sessions milestone
Verified through schema v15:
- explicit CORS allowlist;
- canonical `INARENA_ALLOWED_ORIGINS` production contract;
- request-body size ceiling;
- per-IP/per-session HTTP rate limiting;
- WebSocket origin validation and connection-rate protection;
- standard security response headers;
- Redis-backed rate limiting with safe local fallback;
- local fallback counters reset on application shutdown;
- short-lived scoped operator sessions;
- operator scopes:
  - operator:read
  - operator:write
  - operator:reports
  - operator:recovery
- bootstrap operator key only issues scoped sessions in staging/production;
- direct bootstrap-key access to normal operator APIs is rejected in staging/production;
- frontend operator dashboard exchanges bootstrap key once and stores only the scoped token in sessionStorage;
- staging smoke uses scoped operator authentication.

CI:
- backend suite: PASS;
- PostgreSQL integration: PASS;
- Redis integration: PASS;
- staging smoke: PASS;
- frontend: PASS.

## Quality engineering milestone
Verified:
- Hypothesis property-based evaluator tests;
- 300 randomized five/seven-card evaluator cases;
- integration property test for heads-up chip conservation across valid cash buy-ins;
- Playwright browser E2E gate;
- player OFFLINE/ONLINE shell browser smoke: PASS;
- protected operator route browser smoke: PASS;
- k6 staging load baseline gate;
- k6 HTTP health/readiness/table-read workload: PASS;
- k6 WebSocket connect/reconnect workload: PASS;
- initial load thresholds:
  - HTTP error rate < 1%;
  - HTTP p95 < 500 ms;
  - checks > 99%;
- production container build: PASS.

## Current stage
The project has moved from production hardening into closed-beta readiness.

## Next bounded feature
### Full-stack browser E2E + release candidate gate
Acceptance criteria:
1. Browser E2E runs against a real INARENA backend, not only mocked/static UI.
2. Operator bootstrap login exchanges for a scoped session and loads dashboard data.
3. Operator can create a table through real API and browser refresh keeps scoped session.
4. Authenticated player browser session restores from persisted localStorage session.
5. Player can open ONLINE lobby and see a backend-created table.
6. Cash buy-in/join path is covered end-to-end without duplicate ledger movement.
7. Browser reconnect preserves table state.
8. A release-candidate checklist is generated and CI status is part of the gate.


## Closed-beta readiness milestone
Verified on current release line:
- backend unit/integration suite: PASS;
- property-based poker invariants: PASS;
- PostgreSQL integration: PASS;
- Redis integration: PASS;
- staging smoke: PASS;
- k6 load baseline: PASS;
- production container build: PASS;
- frontend build: PASS;
- Playwright browser smoke: PASS;
- Playwright full-stack browser E2E: PASS.

Full-stack browser coverage now includes:
- operator bootstrap -> scoped session exchange;
- operator dashboard restore from sessionStorage;
- real backend table creation;
- persisted authenticated player session restore;
- ONLINE lobby rendering real backend table;
- internal chip balance display;
- authenticated cash-table seating;
- backend verification of resulting seat/stack.

Release-candidate controls:
- docs/RELEASE_CANDIDATE_CHECKLIST.md
- docs/CLOSED_BETA_PLAN.md

## Current product phase
Closed Beta Readiness / UX & Visual QA.

Backend feature expansion is frozen unless needed for:
- blocker fixes;
- correctness;
- security;
- completion of an already-approved core flow.

## Next bounded feature
### Visual QA + UX state hardening
Acceptance criteria:
1. Validate mobile layouts at 360 / 390 / 430 px.
2. Validate safe areas and Telegram viewport behavior.
3. Validate loading / empty / error / reconnect / expired-session states.
4. Validate 2–9 seat table readability and long player names.
5. Validate operator dashboard desktop/mobile behavior.
6. Add visual regression screenshots for approved Concept 2 states.
7. Resolve critical visual/interaction issues before first internal dry run.


## Visual QA + full-stack beta gate milestone
Verified on current release line:
- approved ONLINE navigation label: Лобби | Игра | Профиль;
- mobile shell hardened for 360 / 390 / 430 px;
- no horizontal overflow in Playwright multi-viewport checks;
- safe-area aware shell padding;
- long table/player/operator text wraps safely;
- compact controls for 360 px;
- operator dashboard expands beyond 430 px on desktop;
- desktop operator metrics/tables use wider responsive grids;
- full-stack browser E2E against real backend: PASS;
- operator bootstrap -> scoped session -> dashboard restore: PASS;
- persisted player session restore -> ONLINE lobby -> cash seating: PASS;
- backend seat/stack verification from browser flow: PASS;
- Playwright browser smoke: PASS;
- frontend CI: PASS;
- backend/property suite: PASS;
- PostgreSQL integration: PASS;
- Redis integration: PASS;
- staging smoke: PASS;
- k6 load baseline: PASS;
- production container build: PASS.

## Current readiness estimate
- technical MVP: ~88%;
- closed-beta readiness: ~85%;
- public production readiness: ~70%.

## Next phase
### Internal dry run + UX polish
Priority:
1. Run full cash-table dry run with 2–6 controlled players.
2. Run full tournament dry run from registration to winner.
3. Capture UX friction and operator interventions.
4. Fix only blocker/critical issues during beta freeze.
5. Complete visual polish and accessibility pass.
6. Publish public staging/preview when hosting access is available.


## Internal dry run + accessibility milestone
Verified on current release line:
- reproducible 6-player cash-table dry run: PASS;
- complete passive hand reaches showdown and settles automatically;
- six-player chip conservation: PASS;
- hand/action history persistence: PASS;
- reproducible 4-player tournament dry run: PASS;
- registration -> seating -> running -> showdown -> finished lifecycle: PASS;
- deterministic winner and finish places 1–4: PASS;
- tournament results report: PASS;
- automated axe WCAG A/AA serious/critical scan: PASS;
- keyboard navigation for player shell/operator login: PASS;
- frontend browser E2E: PASS;
- full-stack browser E2E: PASS;
- backend/property suite: PASS;
- PostgreSQL integration: PASS;
- Redis integration: PASS;
- staging smoke: PASS;
- k6 load baseline: PASS;
- production container build: PASS.

Artifacts:
- docs/INTERNAL_DRY_RUN_RESULTS.md
- docs/CLOSED_BETA_BLOCKERS.md

## Current readiness estimate
- technical MVP: ~92%;
- closed-beta readiness: ~90%;
- public production readiness: ~75%.

## Remaining closed-beta blockers
1. Public HTTPS staging/preview hosting.
2. Real Telegram Mini App dry run on iPhone and Android.
3. Backup/restore drill against the actual hosting PostgreSQL provider.

## Change policy
Backend feature expansion remains frozen except for blocker, correctness,
security, and approved core-flow completion.


## UX state hardening milestone
Verified on current release line:
- explicit ONLINE lobby loading state;
- explicit lobby error state with retry;
- distinct empty-lobby state;
- Telegram authenticating / unavailable / error states;
- reconnect/player-action lock state remains visible;
- scoped operator token expiry is detected;
- expired operator token is removed from sessionStorage;
- operator receives explicit re-authentication message;
- operator logout revokes scoped session and clears local token;
- full-stack browser test covers logout and expired-token recovery;
- automated accessibility gate reports no serious/critical WCAG A/AA violations;
- keyboard navigation for operator login: PASS.

CI on current release line:
- backend suite: PASS;
- property-based poker invariants: PASS;
- PostgreSQL integration: PASS;
- Redis integration: PASS;
- staging smoke: PASS;
- k6 load baseline: PASS;
- production container build: PASS;
- frontend build: PASS;
- browser E2E: PASS;
- full-stack browser E2E: PASS.

## Current readiness estimate
- technical MVP: ~94%;
- closed-beta readiness: ~92%;
- public production readiness: ~76%.

## Remaining beta blockers
1. Public HTTPS staging/preview endpoint.
2. Real Telegram Mini App device dry run on iPhone + Android.
3. Backup/restore drill against the selected hosted PostgreSQL provider.

The connected Vercel integration still reports zero accessible teams.


## Device beta diagnostics milestone
Verified:
- hidden `?diagnostics=1` beta diagnostics screen;
- release/environment metadata from backend;
- Telegram platform/version/theme/viewport diagnostics;
- browser viewport/DPR/language/network diagnostics;
- player authentication status without exposing credentials;
- no Telegram initData, session ID, operator token or private cards in diagnostics;
- 390px browser privacy/layout regression: PASS;
- frontend CI: PASS;
- backend/property/PostgreSQL/Redis/staging/load/backup-restore gates: PASS.

External status:
- Vercel integration checked again: 0 accessible teams;
- public HTTPS preview remains externally blocked;
- real Telegram iPhone/Android device run is ready once public HTTPS exists;
- local PostgreSQL backup/restore drill is PASS;
- hosted PostgreSQL provider drill remains pending.

## Current readiness estimate
- technical MVP: ~96%;
- closed-beta readiness: ~94%;
- public production readiness: ~78%.

## Next action boundary
No new core backend features.
Proceed only with:
1. public HTTPS staging deployment;
2. real Telegram Mini App device dry run;
3. hosted PostgreSQL backup/restore verification;
4. blocker/critical fixes found by those runs.


## RC1 frontend dependency security fix — 2026-10-03

Frozen base: `3761901c4ceff48d6cd187308e8e50cf144753a6`.
Security candidate: `03bbccc33e3a61b67b69e6993e3d3aeb9a89c85d`.
This is a security exception under the beta freeze; no application features,
React ranges, backend code or schema changes.

- Reproduced Render npm audit: 5 vulnerable packages (3 moderate, 1 high, 1 critical).
- Root: Vitest 2.1.9, @vitest/mocker, nested Vite 5.4.21/vite-node/esbuild.
- Pin Vitest 4.1.11, the first maintained fix for GHSA-82fw-gwwq-j7x9;
  also addresses critical GHSA-5xrq-8626-4rwp. Older 2.x/3.x have no mocker fix.
- Pin Vite 6.4.3 within the existing major; fixes GHSA-fx2h-pf6j-xcff,
  GHSA-v6wh-96g9-6wx3 and GHSA-4w7w-66w2-5vf9.
- Add package-lock.json; no blanket audit fix or unrelated dependency range changes.
- npm audit: 0 vulnerabilities; production build: PASS.
- Local Playwright/accessibility: 10 passed; clean fullstack E2E: 3 passed.
- Local backend: 103 passed, 5 infrastructure-dependent skips.
- Same-security-SHA frontend CI: PASS (run 37133242980).
- Same-security-SHA backend CI: PASS (run 37133242984), including PostgreSQL,
  Redis, staging smoke, k6, container build and backup/restore drill.
- npm test has a pre-existing runner-discovery failure: Playwright files are
  collected as Vitest suites; reproduced on both old/new versions. No unit
  test files exist. The required Playwright gates pass.

Audit JSON and RC manifest: `docs/rc1-security/`.
Public Render staging is provisioned; previous public-HTTPS blocker is resolved.
Promotion and post-deploy ready/version/CORS evidence follow the same-SHA gate.
Real Telegram device dry runs and hosted-provider backup/restore remain pending.


### RC1 security staging verification — 2026-10-03

Release `8f938036624b60dfe7524004c28753d7d6056113` passed the existing
RC gate (`scripts/rc_gate.py`) with same-SHA frontend/backend CI.
- Frontend CI: run 37133405626, build/browser/fullstack PASS.
- Backend CI: run 37133405627, all six jobs PASS.
- Render frontend `dep-db0hvfm0tbcc73fud47g`: Live; install found 0 vulnerabilities.
- Render backend `dep-db0hvk0u01pc73afb0ug`: Live; no post-deploy error logs.
- `/ready`: PostgreSQL, schema 15, staging, Redis configured/connected.
- `/version`: exact deployed security release SHA.
- Public frontend: HTTP 200, mobile lobby renders, no page errors or horizontal overflow.
- Browser can fetch backend ready/version across origins.
- CORS allowed frontend preflight: 200 and exact frontend allow-origin.
- CORS untrusted-origin preflight: 400 and no allow-origin header.
- Clean npm ci, audit and TypeScript/Vite build: PASS.

Machine-readable evidence: `docs/rc1-security/staging-verification.json`;
RC manifest: `docs/rc1-security/manifest.json`. These records identify the verified
release; subsequent documentation-only evidence commits require the same CI gate
before advancing the staging branch. No new features were added.


## RC1 Telegram authentication blocker — 2026-10-03

A real iPhone Mini App launch reached the auth endpoint but returned 401.
Code inspection found bot-token HMAC incorrectly removed the modern `signature`
field, confusing the bot-token and third-party Ed25519 validation rules.
The regression test reproduced 401 for valid modern data before the fix.
Keep all fields except `hash` in bot-token HMAC; preserve expiry and tamper checks.
Add rejection logs with only fixed reason category, request ID and release/environment.
No token, initData, user, hashes or signatures enter these diagnostics.
Tests cover modern acceptance, signature tampering and diagnostic privacy.
Same-SHA CI and staging promotion are required; the real device retry remains pending.
Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app


## Approved single-club owner table creation — 2026-10-04

User approved a minimal Dashboard create-table control for the current single club.
The form renders only after successful operator authentication, not in the player
interface or logged-out Dashboard. Uses the existing operator:write endpoint;
no new role model or multi-club ownership claims. Empty names and repeat clicks
while creating are blocked; successful creation refreshes the Dashboard.
Tests verify UI visibility, real creation and backend denial without write access.
Owner bootstrap credentials remain private; future multi-club access needs club scoping.


## Approved player profile beta flow — 2026-10-04

User approved a minimal working Profile to identify players for test-chip credit.
Shows Telegram display name, internal user ID and balance fetched through the
existing authenticated endpoint; manual refresh handles owner credit updates.
Navigation works between home/lobby and Profile. Unimplemented Game/Tournaments
shortcuts are disabled; opening a table remains through the lobby.
No token, session ID or raw Telegram data is displayed. No owner controls are added
to the player interface. Tests cover no-session state, identity/balance, refresh,
return-to-lobby balance and absence of owner controls/session IDs.
Same-SHA CI and staging verification required before promotion.


## 2026-10-04 — approved owner session persistence

Persist only the scoped operator session token across tabs; migrate existing tab sessions on successful validation. Never persist the bootstrap key. Hide bootstrap form while authenticated. Logout and unauthorized/expired responses clear both stores; backend TTL and authorization unchanged. Fullstack coverage verifies reopening, logout and invalid token recovery.


## 2026-10-04 — approved remembered owner login

Owner explicitly requested longer remembered login. Dashboard requests a fixed 30-day scoped session with remember_me=true; API default remains configured short TTL. No bootstrap key persistence, no automatic renewal, existing hashing, scopes, revocation and expiration unchanged. UI communicates 30-day lifetime. Tests cover duration, access after two hours, read-scope restrictions, revocation and default TTL. Existing sessions retain their original expiration.


## 2026-10-04 — owner hand start control

Two staging players seated but active_hand remained null: start requires existing operator endpoint. Expose cash-table start only in authenticated Dashboard; pending and non-open states disable action; display server rejection. No automatic dealing, player privileges, backend source or schema changes. Fullstack covers insufficient players, two-player preflop with 150 blinds pot, disabled duplicate start and absence from player UI.


## 2026-10-04 — two-player cash gameplay loop repaired

Real staging play exposed two RC1 gaps after the owner-start control: player action controls could miss the hand state in Telegram WebView, and completed cash hands stopped at status=open. The repair keeps the first hand operator-controlled, adds a 1s table snapshot fallback alongside WebSocket realtime, uses street contributions for action UI decisions, shows an explicit waiting-for-opponent state, and schedules the next cash hand after a 2s leave window when at least two funded seated players remain. No schema or auth changes.

Evidence: fullstack E2E now uses two isolated player browser contexts and verifies private hole cards, action controls only for the acting seat, observer waiting state, authenticated Fold completion, and automatic transition to a distinct next hand with status=playing and blinds posted. Frontend CI and all backend CI jobs passed on PR #9 before release merge.

## RC1 product-quality milestone — 2026-10-04

Promoted sequentially into `release/closed-beta-rc1`:
- PR #24 — Product Guardian v1.
- PR #25 — private table chat v1.
- PR #26 — safe return-to-table and reconnect feedback.

Current verified RC1 SHA: `8b21bb39935497ea93f0a7002a77dbc2018c4391`.

Same-SHA GitHub CI is fully green:
- backend test;
- PostgreSQL integration;
- Redis integration;
- load smoke;
- staging smoke;
- backup/restore drill;
- frontend build;
- fullstack E2E;
- Product Guardian journeys.

### Current bounded increment

Branch `feat/owner-quick-credit-v1`:
- quick test-chip presets +1,000 / +5,000 / +10,000 by Player ID;
- visible resulting balance;
- existing manual delta tool retained;
- owner table filters: All / Live / Open / Paused / Closed;
- desktop + mobile Guardian journey with a 5s quick-credit budget;
- no backend, schema, ledger, role or deployment changes.

### Next

1. Pass backend/frontend/Product Guardian CI for Owner Quick Credit on one PR SHA.
2. Promote only after the candidate SHA is green.
3. Run the real Telegram/iPhone two-player closed-beta dry run.
4. Continue network/reconnect diagnostic hardening from observed test-session friction.

No production deployment is authorized by this checkpoint.

