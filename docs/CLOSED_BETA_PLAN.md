# INARENA Closed Beta Plan

## Goal
Validate the product with a controlled group before public production.

## Phase 1 — Internal dry runs
Participants:
- operator/admin
- 2–6 controlled test players

Scenarios:
- cash seating / leave / waitlist
- heads-up and 3+ player hands
- all-in / side-pot hands
- reconnect during action
- timeout action
- tournament registration and late registration
- rebuy / add-on
- tournament finish / ranking
- operator recovery

## Phase 2 — Small closed beta
Target:
- 10–30 invited users
- limited number of tables
- no public acquisition

Measure:
- session/auth failures
- reconnect frequency
- action latency
- WebSocket disconnects
- table occupancy
- failed mutations
- idempotency replays
- outbox backlog
- DB pool pressure
- operator interventions

## Phase 3 — Extended closed beta
Target:
- multiple concurrent tables
- realistic tournament duration
- multi-instance backend validation

Exit only after:
- stable chip accounting
- acceptable p95 action latency
- no unresolved critical security issues
- operator workflow proven
- UX pain points documented and addressed

## Change policy during beta
Feature expansion is frozen unless:
- required to fix a blocker;
- required for safety/security;
- required to complete an already-approved core flow.

All other ideas go to the post-beta backlog.
