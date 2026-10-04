# INARENA development priorities

Continue feature development and quality controls together. Every new feature
gets a user-visible acceptance journey in Guardian; checkpoints save progress,
not automatically pause the agreed work.

## Current reviewable increment

PR #24: critical journeys, READY/WARNING/BLOCKED release report, failure evidence,
initial timing budgets, targeted mobile usability checks, and profile Copy ID
for test-chip credit. No merge or deployment performed.

Table chat v1 follows as a separate increment: private seated-player access,
recent history, unread feedback, network recovery and a database-backed send
throttle. It uses one-second REST refresh and adds desktop/mobile Guardian
journeys; implementation and limits are documented in table-chat.md.

## Next small increments

1. Review and promote Guardian through same-SHA CI; require journeys in repository
   branch protection, and perform the real Telegram/iPhone two-player dry run.
2. Verify and promote table chat v1 with the Guardian increment; add richer chat
   controls only when closed-beta use demonstrates a need.
3. Return-to-table convenience and clearer waiting/reconnect feedback, based on
   observed test-session friction; preserve financial and participation semantics.
4. Owner conveniences for test-chip credit and table visibility, using current
   single-club roles rather than adding club-management infrastructure.
5. Strengthen Guardian: network interruption journeys, correlated frontend/API/
   game-engine diagnostics, more mobile critical actions, then baseline performance
   comparison once a stable environment exists.

Real User Intelligence/session analytics are deferred until closed-beta users
exist. No PostHog or OpenTelemetry rollout is required to deliver these increments.
Existing backend observability and browser traces are the initial diagnostic tools.
The ordering is a working plan, not permission for production deployment or messages
to users. Report confirmed results and concrete blockers without asking for a new
"continue" after each checkpoint.
