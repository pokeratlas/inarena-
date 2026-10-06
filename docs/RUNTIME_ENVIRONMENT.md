# INARENA Runtime Environment Contract

## Required production environment
- INARENA_DATABASE_URL
- INARENA_OPERATOR_KEY
- INARENA_ALLOWED_ORIGINS

## Optional
- INARENA_REDIS_URL
- TELEGRAM_BOT_TOKEN
- INARENA_ACTION_TIMEOUT_SECONDS
- INARENA_SEAT_RESERVATION_SECONDS
- INARENA_SESSION_TTL_SECONDS
- INARENA_OPERATOR_SESSION_TTL_SECONDS
- INARENA_LOG_LEVEL
- INARENA_RELEASE
- INARENA_ENV
- INARENA_DB_POOL_MIN
- INARENA_DB_POOL_MAX
- INARENA_DB_POOL_TIMEOUT_SECONDS

## Modes
`INARENA_ENV`:
- development
- test
- staging
- production

Production must never enable:
`INARENA_ENABLE_LEGACY_API=1`

## Health contract

### /health
Process liveness only.

### /ready
Readiness checks:
- schema can be read;
- primary database can execute a query;
- required production configuration is present.

Redis is initially reported separately and is not a hard readiness dependency until multi-instance coordination is enabled.

## Secrets
Secrets are environment/runtime secrets.
They are never committed to Git or embedded into frontend bundles.


## PostgreSQL pool
Production defaults:
- minimum connections: 2
- maximum connections: 10
- acquisition/startup timeout: 5 seconds

Tune these values against the hosting provider connection limit.
Each API transaction borrows a pooled connection and returns it when the transaction closes.


## Observability
HTTP responses include `X-Request-ID`.
A valid inbound `X-Request-ID` is preserved; otherwise the backend generates one.

Structured HTTP logs include only:
- request ID;
- method;
- path;
- response status;
- duration;
- environment.

Request/response bodies, session IDs, authorization headers, operator keys,
Telegram initData and private cards are not included in request logs.

`INARENA_RELEASE` should be set to the deployed Git commit or release identifier.
The public `/version` endpoint exposes only release identifier and environment.
Operator-only `/api/v1/operator/diagnostics` exposes database, realtime and
outbox health without secrets.


## Operator authentication
`INARENA_OPERATOR_KEY` is a bootstrap credential.
Operator clients should exchange it for a short-lived scoped session token and
store only the token for the active browser session.

Default operator session TTL: 3600 seconds.
Supported scopes:
- operator:read
- operator:write
- operator:reports
- operator:recovery

The bootstrap key may only issue scoped operator sessions in staging and production.
Direct operator API access with the bootstrap key is rejected outside development/test.

## CORS / browser boundary
`INARENA_ALLOWED_ORIGINS` is the canonical comma-separated explicit allowlist.
Production readiness rejects wildcard `*`.
Telegram Mini App embedding is intentionally not blocked with X-Frame-Options.


## Security perimeter
Optional controls:
- `INARENA_MAX_REQUEST_BODY_BYTES` — default 1 MiB;
- `INARENA_RATE_LIMIT_AUTH_PER_MINUTE` — default 30;
- `INARENA_RATE_LIMIT_OPERATOR_PER_MINUTE` — default 60;
- `INARENA_RATE_LIMIT_PLAYER_PER_MINUTE` — default 180;
- `INARENA_RATE_LIMIT_WS_PER_MINUTE` — default 30;
- `INARENA_TRUST_PROXY_HEADERS=1` only behind a trusted reverse proxy.

`INARENA_CORS_ORIGINS` is accepted only as a temporary compatibility alias.
New deployments should use `INARENA_ALLOWED_ORIGINS`.
