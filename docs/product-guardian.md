# Product Guardian v1

A deterministic release check built from the existing Playwright fullstack suite.
No AI service, production credentials, new database, telemetry, or deployment step.
Baseline: release/closed-beta-rc1, PR #23, dc68d88.

## Required journeys

Desktop runs all 16 existing fullstack scenarios: owner session persistence,
invalid session recovery, player restored session/lobby/buy-in/join, profile and
balance, protected owner creation with blinds and buy-in bounds, live owner hand,
two-player autostart and next hand, watchdog, leave after settlement, public
identity privacy, sit-out/return, immediate and queued top-up, showdown/reconnect/
settlement/exit, fixed seven-max, owner pause/reopen/close.

Mobile Chromium (390px, touch/device emulation) repeats join, owner creation,
live hand and pause/reopen/close. This is not an iPhone Telegram/WebKit dry run.
API calls prepare test players/chips; UI actions exercise the existing player
and owner controls. The showdown acceptance also checks authenticated APIs.
Telegram HMAC validation remains in backend tests; real device validation remains
a separate closed-beta requirement. Chat is not implemented or claimed by v1.

## Gate policy

- READY: all 20 required project/journey pairs pass on their first attempt.
- WARNING: all pass, but at least one needs a retry. Investigate and rerun cleanly.
- BLOCKED: failed, timed out, skipped, missing, duplicated or incomplete journey,
  missing/invalid report, or runner/setup error.

Only READY exits zero. WARNING and BLOCKED stop automatic release. The JSON/Markdown
report records the exact checked-out SHA, every journey, and actionable reasons.
`scripts/rc_gate.py` additionally requires successful backend-ci, frontend-ci and
product-guardian on the candidate SHA, including every required job. Old successful
runs cannot override a newer failure or pending run. The existing PASS RC manifest
remains compatible and adds `product_guardian: READY`.

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
names. One worker limits shared-backend contention. Existing frontend/fullstack
commands remain available. Production frontend/backend source and schema are unchanged.

## CI and evidence

`product-guardian.yml` runs on PRs, main/RC1 pushes and manual dispatch. It uploads
gate JSON/Markdown, Playwright JSON/HTML, and retained failure artifacts even when
tests fail. Trace/screenshots include manually created multiplayer contexts;
video covers runner-managed page contexts (owner and player join). Keep artifacts
14 days. Test sessions and operator keys are disposable local fixtures; traces
can contain them, so artifacts must never use production credentials.

The existing frontend workflow still runs shell/mobile/accessibility smoke and
the original fullstack suite; backend CI keeps integration, load and restore gates.
Guardian adds a unified user-journey report rather than replacing these checks.
Run the release-candidate workflow only after all three workflows finish on the
candidate SHA. Repository branch protection must require `journeys` alongside
existing checks; this code does not change repository settings or promote RC1.
