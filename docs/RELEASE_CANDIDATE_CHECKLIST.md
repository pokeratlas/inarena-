# INARENA Release Candidate Checklist

## Scope
This checklist is the gate for a closed-beta release candidate.

## Required CI
All must be green on the same commit:
- backend unit/integration suite
- PostgreSQL integration
- Redis integration
- staging smoke
- k6 load-smoke
- production container build
- frontend TypeScript/Vite build
- Playwright browser smoke
- Playwright full-stack browser E2E

## Backend correctness
- server-authoritative NL Hold'em runtime
- blinds/button/action sequencing
- min-raise / all-in / side pots
- automatic showdown / uncontested settlement
- chip conservation property tests
- transactional realtime outbox
- crash-safe idempotency receipts
- reconnect/replay
- timeout policy
- no private-card leakage

## Data layer
- PostgreSQL schema current
- ordered migration runner passes
- backup/restore procedure documented
- Redis remains non-authoritative
- DB pool within configured bounds

## Security
- legacy mutation API disabled outside test/development
- explicit production CORS allowlist
- request-body limit enabled
- HTTP rate limits enabled
- WebSocket origin/rate protection enabled
- scoped operator sessions used in staging/production
- bootstrap operator key used only to issue scoped sessions
- secrets absent from frontend bundle/logs
- operator audit enabled

## Player UX
- Telegram session restore works
- OFFLINE / ONLINE switch works
- lobby loads backend data
- cash balance visible
- authenticated cash seating works
- tournament registration lifecycle works
- waitlist/reservation flow works
- table reconnect does not duplicate actions
- action timer reflects server deadline

## Operator UX
- bootstrap login exchanges for scoped token
- token survives page refresh in sessionStorage
- dashboard loads real backend data
- table controls work
- tournament controls work
- rebuy/add-on window controls work
- audit/report access works
- session revoke/logout path verified

## Visual QA
Must be reviewed on:
- iPhone 390px
- iPhone 430px
- Android ~360px
- desktop operator dashboard

Review:
- typography
- spacing
- safe areas
- table legibility
- action controls
- loading/error/empty states
- reconnect state
- long player names
- 7-seat table density

## Closed-beta exit criteria
- no blocker/critical bugs open
- no chip-accounting invariant failures
- no private-data leakage
- no duplicate player mutations
- reconnect/recovery verified
- staging backup restore drill completed
- operator can recover a stuck table
- at least one end-to-end tournament dry run completed
- at least one end-to-end cash-table dry run completed

## Release decision
A release candidate is beta-ready only when all mandatory sections above are verified against one commit SHA.
