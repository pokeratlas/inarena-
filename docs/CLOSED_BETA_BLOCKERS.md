# INARENA Closed-Beta Blockers

## Blocking before invited-user beta

### 1. Public staging / preview hosting
Status: BLOCKED EXTERNALLY.

Vercel connection was rechecked on 2026-10-02 and still exposes no accessible team/account.

The application is now provider-neutral:
- Docker production backend;
- PostgreSQL 16;
- Redis 7;
- explicit migration-before-start;
- HTTPS/CORS contract;
- staging smoke/full-stack E2E;
- provider-neutral requirements in `docs/HOSTING_REQUIREMENTS.md`.

A Render integration is available as an alternative deployment path once connected.

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

Automated CI creates meaningful INARENA state, performs pg_dump,
restores into a clean PostgreSQL database, verifies migrations and checks
restored domain data. The remaining requirement is repeating the same drill
against the selected hosted PostgreSQL provider.

## Beta operations readiness
Ready:
- release-candidate checklist;
- machine-enforced RC workflow;
- beta bug/UX issue forms;
- P0-P3 triage policy;
- beta handoff runbook;
- hidden privacy-safe device diagnostics screen;
- internal cash/tournament dry runs;
- accessibility/browser/full-stack/load gates.

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
