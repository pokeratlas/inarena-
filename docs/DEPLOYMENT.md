# INARENA Deployment Runbook

## Release contract
Staging and production use:
- PostgreSQL as the authoritative database;
- Redis for realtime fan-out / ephemeral coordination;
- the backend production container;
- runtime secrets supplied by the hosting platform.

SQLite is local-development only.

## Pre-deploy
1. Confirm backend/frontend CI is green.
2. Confirm PostgreSQL integration, Redis integration and staging smoke jobs are green.
3. Create a verified PostgreSQL backup for production schema changes.
4. Record target commit SHA and current schema version.
5. Confirm `INARENA_ENABLE_LEGACY_API` is disabled.

## Migration gate
Before API traffic is served:

```bash
python -m app.migrate upgrade
python -m app.migrate check
```

The production container entrypoint runs `upgrade` automatically before starting Uvicorn.

A failed migration must prevent the application process from starting.

## Staging
Use:

```bash
docker compose --env-file deploy/staging.env -f deploy/docker-compose.staging.yml up --build
```

Then run:

```bash
python backend/scripts/staging_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --operator-key "$INARENA_OPERATOR_KEY"
```

Staging must validate:
- liveness;
- readiness;
- auth boundaries;
- operator table lifecycle;
- WebSocket snapshot;
- PostgreSQL connectivity;
- Redis connectivity.

## Production rollout
Recommended sequence:
1. Put release into maintenance/no-new-writes mode if the migration is not backward compatible.
2. Create and verify pre-migration backup.
3. Deploy the new backend image.
4. Run migration gate.
5. Wait for `/ready`.
6. Run smoke tests against the production endpoint.
7. Enable traffic gradually where the platform supports it.
8. Monitor errors, database pool pressure and realtime delivery.
9. Mark release complete only after operator verification.

## Rollback
Application rollback is allowed only when the previous application version supports the current database schema.

Never automatically downgrade PostgreSQL schema.

If the release fails after a forward-only migration:
- stop write traffic;
- investigate compatibility;
- roll forward with a corrective release where possible;
- restore a verified backup only when an explicit data rollback is required.

## Required secrets
- `INARENA_DATABASE_URL`
- `INARENA_REDIS_URL`
- `INARENA_OPERATOR_KEY`
- `TELEGRAM_BOT_TOKEN` when Telegram auth is enabled

## Observability before public launch
Required:
- structured application logs;
- error tracking;
- database-pool metrics;
- Redis connectivity metrics;
- WebSocket connection/event metrics;
- migration version in deployment metadata.
