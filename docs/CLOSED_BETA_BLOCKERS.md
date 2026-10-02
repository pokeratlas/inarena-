# INARENA Closed-Beta Blockers

## Blocking before invited-user beta

### 1. Public staging / preview hosting
Status: BLOCKED EXTERNALLY.

Current connected Vercel integration exposes no accessible team/account.
A public HTTPS frontend + persistent backend endpoint is required for real-device beta.

### 2. Real Telegram device dry run
Required:
- iPhone Telegram Mini App;
- Android Telegram Mini App;
- session restore after app close/reopen;
- background/foreground reconnect;
- network handoff Wi-Fi <-> cellular.

Status: NOT YET VERIFIED ON REAL DEVICES.

### 3. Backup / restore drill on actual production-like PostgreSQL
Run:
- create backup;
- verify backup;
- restore into clean database;
- run migrations/check;
- run smoke suite.

Status: RUNBOOK READY; PROVIDER DRILL PENDING.

## Non-blocking but required before public production

### Accessibility
Automated axe serious/critical WCAG checks are enabled.
Manual VoiceOver/TalkBack review remains.

### Visual polish
Concept 2 is stable at 360 / 390 / 430 px and operator desktop widths.
Fine typography/spacing polish remains.

### Observability provider
Structured logs and diagnostics exist.
External error/trace aggregation still needs the selected hosting/monitoring account.

### Closed-beta evidence
Target:
- 10–30 invited users;
- multiple concurrent tables;
- one realistic-duration tournament.

Metrics to capture:
- auth/session failures;
- reconnects;
- action latency;
- failed mutations;
- idempotency replays;
- outbox backlog;
- DB pool pressure;
- operator interventions.

## Current release discipline
Backend feature expansion remains frozen except:
- blocker fixes;
- correctness;
- security;
- completion of approved core flow.
