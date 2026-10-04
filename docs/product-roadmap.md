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
- Network Recovery v1: active-hand offline gap, locked disconnected actions,
  bounded reconnect, request-ID correlation and duplicate-action protection in
  both desktop and mobile Guardian projects.

These increments were promoted sequentially only after same-SHA CI gates passed.

## Current milestone

Real Telegram/iPhone two-player dry run on public staging. Preserve evidence for:
authentication/session restore, OFFLINE -> ONLINE, seating, private cards, action
controls, automatic next hand, background/foreground recovery, forced network
loss/recovery, chat, return-to-table and clean table exit.

Public staging is available for this milestone. The remaining verification is
real-device behavior; browser emulation does not substitute for it.

## Next small increments

1. Complete and record the real Telegram/iPhone two-player dry run.
2. Fix only concrete blocker/correctness/UX issues observed in the dry run.
3. Repeat the hosted PostgreSQL backup/restore drill against the selected staging
   database before invited-user beta.
4. Establish performance baselines after a stable closed-beta environment exists.
5. Add richer chat or owner controls only from observed closed-beta friction.

Real User Intelligence/session analytics remain deferred until closed-beta users
exist. No PostHog or OpenTelemetry rollout is required yet. Existing backend
observability, request IDs and browser traces remain the initial diagnostic tools.
No production deployment or public user messaging is implied by this roadmap.
