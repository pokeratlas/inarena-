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
- Telegram Fast Bootstrap: dismisses Telegram's native loader before backend
  authentication completes and removes the redundant stored-session request.

## Verified real-device milestone

A controlled real iPhone Telegram Mini App run was reported PASS on 2026-10-05
against RC1 `0c4067fd`. No blocking startup, authentication, lobby, gameplay,
chat, reconnect, return-to-table, chip-accounting or mobile-layout problem was
reported in that run.

## Current milestone

Complete the remaining invited-beta prerequisites:
1. Android real-device Telegram Mini App run.
2. Hosted PostgreSQL backup/restore drill against the selected staging database.
3. Preserve release-candidate evidence on the exact invited-beta SHA.

## Next small increments

1. Fix only blocker/correctness/UX issues observed in remaining device/infrastructure checks.
2. Start a small closed beta with 10–30 invited users after all blocking prerequisites pass.
3. Establish performance baselines from real closed-beta traffic.
4. Add richer chat or owner controls only from observed closed-beta friction.

Real User Intelligence/session analytics remain deferred until closed-beta users
exist. No PostHog or OpenTelemetry rollout is required yet. Existing backend
observability, request IDs and browser traces remain the initial diagnostic tools.
No production deployment or public user messaging is implied by this roadmap.
