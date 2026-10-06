# INARENA Closed-Beta Blockers

## Blocking before invited-user beta

### 1. Public staging / preview hosting
Status: READY FOR CONTROLLED DEVICE TESTING.

Public staging is available on Render:
- frontend: `https://inarena-frontend.onrender.com`;
- backend: `https://inarena-backend.onrender.com`;
- source branch: `release/closed-beta-rc1`.

Both services were verified live from the same RC1 commit on 2026-10-05.
Backend auto-deploy is enabled. Frontend auto-deploy is disabled, so every RC
promotion must include an explicit frontend staging deploy before device testing.

The application remains provider-neutral:
- Docker production backend;
- PostgreSQL 16;
- Redis 7;
- explicit migration-before-start;
- HTTPS/CORS contract;
- staging smoke/full-stack E2E;
- provider-neutral requirements in `docs/HOSTING_REQUIREMENTS.md`.

### 2. Real Telegram device dry run
Required:
- iPhone Telegram Mini App;
- Android Telegram Mini App;
- session restore after app close/reopen;
- background/foreground reconnect;
- network handoff Wi-Fi <-> cellular.

Status: IPHONE PASS; ANDROID PENDING.

A controlled Telegram Mini App run on a real iPhone was reported PASS on
2026-10-05 after the fast-bootstrap fix in RC1 `0c4067fd`. No blocking auth,
gameplay, reconnect, chat, chip-accounting or layout issue was reported.
Android still requires a real-device run before the full device matrix is complete.

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
