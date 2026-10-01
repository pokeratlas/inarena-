# INARENA Runtime Environment Contract

## Required production environment
- INARENA_DATABASE_URL
- INARENA_OPERATOR_KEY

## Optional
- INARENA_REDIS_URL
- TELEGRAM_BOT_TOKEN
- INARENA_ACTION_TIMEOUT_SECONDS
- INARENA_SEAT_RESERVATION_SECONDS
- INARENA_SESSION_TTL_SECONDS
- INARENA_LOG_LEVEL
- INARENA_ENV

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
