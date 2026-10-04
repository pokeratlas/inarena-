# INARENA development priorities

Continue feature development and quality controls together. Every new feature
gets a user-visible acceptance journey in Guardian; checkpoints save progress,
not automatically pause the agreed work.

## Promoted into RC1

- Product Guardian v1: deterministic READY / WARNING / BLOCKED release gate,
  failure evidence, timing budgets, mobile usability checks and Profile Copy ID.
- Table chat v1: private seated-player chat, bounded history, unread feedback,
  reconnect recovery, send throttle and desktop/mobile Guardian coverage.
- Return-to-table v1: authenticated seat shortcut, fresh membership validation,
  reconnect feedback and sit-out-safe return behavior.
- Owner Quick Credit v1: Player ID quick credit presets, authoritative resulting
  balance, existing audited ledger mutation, and Table Manager status filters.

These increments were promoted sequentially only after same-SHA CI gates passed.

## Current reviewable increment

Network Recovery v1 extends Product Guardian around a live cash hand. It forces a
browser offline gap while the disconnected player is the actor, verifies action
controls are locked, advances the authoritative server state with an idempotent
mutation carrying a request ID, reconnects, checks the client catches up to the
next hand within budget, and proves the fold was recorded exactly once. Desktop
and mobile Guardian projects both require the journey.

No game-rule, schema, ledger, role, deployment or production semantics change.

## Next small increments

1. Verify and promote Network Recovery v1 through same-SHA backend/frontend/Guardian CI.
2. Perform the real Telegram/iPhone two-player dry run and preserve its evidence.
3. Add deeper frontend/API/game-engine correlation only where the dry run exposes
   diagnostic gaps; existing request IDs, structured logs and browser traces remain
   the starting point.
4. Establish performance baselines after a stable closed-beta environment exists.
5. Add richer chat or owner controls only from observed closed-beta friction.

Real User Intelligence/session analytics remain deferred until closed-beta users
exist. No PostHog or OpenTelemetry rollout is required yet. Existing backend
observability and browser traces remain the initial diagnostic tools. No production
deployment or user messaging is implied by this roadmap.
