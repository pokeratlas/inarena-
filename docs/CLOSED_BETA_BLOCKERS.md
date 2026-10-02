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

Status: LOCAL POSTGRESQL BACKUP/RESTORE DRILL PASS; HOSTED PROVIDER DRILL PENDING.

Automated CI now creates meaningful INARENA state, performs pg_dump,
restores into a clean PostgreSQL database, verifies migrations and checks
restored domain data. The remaining requirement is repeating the same drill
against the selected hosted PostgreSQL provider.

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


### Device diagnostics
Status: READY.

A hidden beta diagnostics screen is available at:
`?diagnostics=1`

It exposes only safe troubleshooting context:
- release/environment;
- Telegram WebApp availability/platform/version/theme;
- Telegram viewport/stable viewport;
- browser viewport/DPR/language/network state;
- authentication status/provider.

It intentionally excludes:
- Telegram initData;
- player session IDs;
- operator tokens;
- private cards;
- authorization headers.

Use together with `docs/BETA_DEVICE_RUNBOOK.md`.
