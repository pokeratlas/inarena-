# INARENA Render Staging Launch

## Blueprint
The repository root contains `render.yaml`.

It defines:
- `inarena-backend` — persistent Docker web service;
- `inarena-frontend` — Vite static site;
- `inarena-postgres` — managed PostgreSQL;
- `inarena-redis` — managed Key Value / Redis.

Cross-service URLs are wired automatically:
- frontend `VITE_API_BASE` <- backend `RENDER_EXTERNAL_URL`;
- backend `INARENA_ALLOWED_ORIGINS` <- frontend `RENDER_EXTERNAL_URL`;
- backend `INARENA_RELEASE` <- backend `RENDER_GIT_COMMIT`.

## One-time secret inputs
Render must receive:
- `INARENA_OPERATOR_KEY`;
- `TELEGRAM_BOT_TOKEN` for real Telegram authentication.

Do not commit either value.

## Launch sequence
1. Create/sync a Render Blueprint from this repository's `render.yaml`.
2. Supply the two secret values above.
3. Wait for PostgreSQL and Redis provisioning.
4. Wait for backend deployment.
5. Backend entrypoint runs ordered migrations before Uvicorn.
6. Verify backend `/ready`.
7. Wait for frontend static build.
8. Open frontend HTTPS URL.
9. Confirm operator bootstrap -> scoped session login.
10. Run staging smoke against the public backend URL.
11. Run full-stack browser E2E against the public frontend/backend.
12. Configure the frontend HTTPS URL as the Telegram Mini App URL.
13. Begin iPhone + Android device dry run.

## Required checks before device beta
Backend:
- `/health` -> 200
- `/ready` -> ready
- `/version` -> expected release SHA/environment
- PostgreSQL schema is current
- Redis coordination is configured
- outbox backlog is near zero

Frontend:
- no mixed-content requests;
- API requests target HTTPS backend;
- WebSocket upgrades use WSS;
- ONLINE lobby loads;
- operator route exchanges bootstrap key for scoped token.

## Failure policy
If backend migration fails:
- do not serve beta traffic;
- inspect deployment logs;
- do not reset the production/staging database destructively.

If frontend cannot reach backend:
- verify `VITE_API_BASE` in the static-site build;
- verify backend `INARENA_ALLOWED_ORIGINS`;
- rebuild the frontend after environment changes.

If WebSocket fails:
- verify browser Origin matches the frontend Render URL;
- verify WSS upgrade through Render;
- inspect operator diagnostics and backend logs.

## Beta freeze
Once public staging is live, no feature expansion.
Only P0/P1 correctness/security/core-flow fixes are allowed until closed-beta exit criteria are met.
