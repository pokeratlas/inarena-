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

These increments were promoted sequentially only after same-SHA CI gates passed.

## Current reviewable increment

Owner Quick Credit v1 adds a focused owner workflow on top of the existing audited
operator balance mutation: Player ID entry, +1k / +5k / +10k test-chip presets,
visible resulting balance, and table filters for All / Live / Open / Paused / Closed.
The existing manual delta tool remains available. No backend/schema/ledger/role
semantics change. See `docs/owner-quick-credit.md`.

## Next small increments

1. Verify and promote Owner Quick Credit through same-SHA backend/frontend/Guardian CI.
2. Perform the real Telegram/iPhone two-player dry run and preserve its evidence.
3. Strengthen Guardian with broader network interruption journeys and correlated
   frontend/API/game-engine diagnostics.
4. Establish performance baselines after a stable closed-beta environment exists.
5. Add richer chat or owner controls only from observed closed-beta friction.

Real User Intelligence/session analytics remain deferred until closed-beta users
exist. No PostHog or OpenTelemetry rollout is required yet. Existing backend
observability and browser traces remain the initial diagnostic tools. No production
deployment or user messaging is implied by this roadmap.
