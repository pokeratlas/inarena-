# INARENA Closed-Beta Handoff

## Tester entry
Use only the supplied HTTPS beta URL from the operator.

For Telegram Mini App testing:
- open the bot from the intended Telegram account;
- reproduce issues on the same device when possible;
- use `?diagnostics=1` only when asked for troubleshooting.

## Before a beta session
Operator verifies:
- release candidate SHA;
- /ready = ready;
- operator scoped session works;
- PostgreSQL/Redis diagnostics are healthy;
- realtime outbox backlog is normal;
- backup exists for production-like hosted DB once hosting is connected.

## During a beta session
Record:
- number of active users/tables;
- authentication failures;
- reconnects;
- failed mutations;
- operator interventions;
- abnormal latency;
- any P0/P1 issue.

## Tester bug reporting
Use GitHub Closed Beta Bug / UX Feedback forms.
For technical bugs include the privacy-safe diagnostics payload and request ID.

## Stop conditions
Stop the affected flow immediately on:
- chip/accounting mismatch;
- duplicate mutation;
- private data exposure;
- unauthorized action;
- unrecoverable table state;
- suspected database corruption.

## Current external prerequisites
Before invited-user device beta:
1. public HTTPS frontend/backend;
2. Telegram Mini App configured to that HTTPS URL;
3. hosted PostgreSQL backup/restore drill;
4. iPhone + Android real-device run.

## Release candidate evidence
Run the GitHub `release-candidate` workflow against the intended commit.
Keep the generated RC artifact with the beta session notes.
