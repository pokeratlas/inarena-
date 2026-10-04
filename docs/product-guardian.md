# Product Guardian v1 — journeys, timing and mobile usability

A deterministic release check built from the existing Playwright fullstack suite.
No AI service, production credentials, new database, telemetry, or deployment step.

## Required journeys

Guardian now treats complete player and owner workflows as the release contract.
Desktop covers 21 journeys: owner session/recovery/create/live/lifecycle, authenticated
join/profile/identity, cash autostart/watchdog/leave/sit-out/top-up/showdown acceptance,
fixed seven-max, private table chat, safe return-to-table, Owner Quick Credit, active-hand network recovery, and the Table V2 seven-max visual contract.

Mobile Chromium (iPhone 13 viewport/touch emulation) repeats ten critical journeys:
join, owner creation, live owner view, owner lifecycle, table chat, return-to-table,
Owner Quick Credit, active-hand network recovery, Table V2 layout, and Profile V2. This remains browser emulation rather than a real Telegram
iPhone/WebKit dry run; real-device validation is a separate closed-beta requirement.

API calls prepare disposable test users/tables/chips. User-visible actions are still
performed through the UI. Telegram HMAC validation remains in backend tests.

## Gate policy

- READY: all 31 required project/journey pairs pass on their first attempt.
- WARNING: all pass, but at least one needs a retry. Investigate and rerun cleanly.
- BLOCKED: failed, timed out, skipped, missing, duplicated or incomplete journey,
  missing/invalid report, runner/setup error, missing/invalid required measurement,
  or elapsed time exceeding the configured budget.

## Timing and usability increment

`frontend/e2e-fullstack/guardian-budgets.json` is the shared budget source for
Playwright and the release report. Current development/CI ceilings include:
lobby ready 5s, selected buy-in to seated 8s, owner create 5s, Fold to actionable
next hand 10s, chat delivery 5s, return-to-table 8s, Owner Quick Credit 5s, and active-hand reconnect 8s.
These are development ceilings, not production latency SLOs.

Critical controls must be visible, enabled, at least 36px in both dimensions, and
unobstructed at their center after scrolling; the page must have no horizontal
overflow. This targeted automated UX check does not replace a real-device review.
A stricter 44px design target remains a future UI hardening step.

Profile Copy ID is verified with real clipboard content and denied-clipboard recovery.
Owner Quick Credit uses that ID with the existing audited balance mutation and keeps
manual delta adjustment available for advanced corrections. Chat/return journeys
verify reconnect behavior and preserve membership/participation semantics. Network Recovery
forces an active-hand offline gap, confirms action controls lock while disconnected,
checks request-ID correlation for the server-side mutation, and verifies exactly one fold
after the client catches up to the next hand.

Only READY exits zero. WARNING and BLOCKED stop automatic release. The JSON/Markdown
report records the exact checked-out SHA, every journey, timing measurements and
actionable reasons. `scripts/rc_gate.py` additionally requires successful backend-ci,
frontend-ci and product-guardian on the candidate SHA, including every required job.
Old successful runs cannot override a newer failure or pending run.

## Run locally

Install the existing backend dev dependencies and frontend lockfile dependencies;
install Playwright Chromium. Start the backend on 127.0.0.1:8000 with a fresh
throwaway SQLite database and the same env as the product-guardian workflow.
Never point these fixtures at a real club database. Then:

```sh
cd frontend
npm run guardian
cd ..
python scripts/guardian_gate.py --report frontend/guardian-results/playwright.json \
  --sha "$(git rev-parse HEAD)" --output frontend/guardian-results/gate.json
python -m unittest discover -s scripts -p 'test_*gate.py'
```

Use a fresh database for each complete run; projects/retries use distinct table
names. One worker limits shared-backend contention.

## CI and evidence

`product-guardian.yml` runs on PRs, main/RC1 pushes and manual dispatch. It uploads
gate JSON/Markdown, Playwright JSON/HTML, and retained failure artifacts even when
tests fail. Artifacts are retained 14 days. Test sessions and operator keys are
disposable local fixtures; production credentials must never be used.

The frontend workflow still runs build/fullstack/mobile/accessibility checks; backend
CI keeps PostgreSQL, Redis, load and restore gates. Guardian is the unified user-
journey decision layer, not a replacement for those checks. RC1 promotion is allowed
only after all required workflows are green on the same candidate SHA.
