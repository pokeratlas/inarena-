# Product Guardian v1 — journeys, timing and mobile usability

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
  missing/invalid report, runner/setup error, missing/invalid required measurement,
  or elapsed time exceeding the configured budget.

## Timing and usability increment

`frontend/e2e-fullstack/guardian-budgets.json` is the shared budget source for
Playwright and the release report: lobby ready 5s, selected buy-in to seated 8s,
owner create to visible card 5s, Fold to actionable next hand 10s. These are
initial ceilings in the local/CI development environment, not production latency
SLOs or a comparison with a stable production baseline. Time starts immediately
before the relevant UI action and stops after the visible outcome. Report includes
actual duration and budget for desktop and applicable mobile journeys.

Join presets/confirmation and owner create controls must be visible, enabled,
at least 36px in both dimensions, and unobstructed at their center after scrolling;
the page must have no horizontal overflow. This targeted automated UX check does
not claim a full UX review; a 44px design target and real-device review are future work.
Playwright output folders are excluded from Vite watching to prevent trace HTML
from causing application reloads while the suite runs.

Profile now provides Copy ID with accessible success/failure feedback. Its journey
checks the real clipboard content and denied-clipboard recovery; credentials remain
absent from the profile. No real-user analytics are installed before beta users exist.

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
