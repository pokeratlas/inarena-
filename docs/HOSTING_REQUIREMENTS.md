# INARENA Hosting Requirements

## Goal
Run closed-beta and production without coupling the application architecture to one hosting vendor.

## Frontend
Requirements:
- HTTPS;
- static Vite/React hosting;
- custom environment variable `VITE_API_BASE`;
- browser origin included in backend `INARENA_ALLOWED_ORIGINS`.

## Backend
Requirements:
- long-running container/service;
- WebSocket support;
- Docker image support;
- HTTPS termination;
- health check against `/health`;
- readiness check against `/ready`;
- runtime environment variables;
- no serverless-only sleep/ephemeral lifecycle for the realtime runtime.

## PostgreSQL
Requirements:
- PostgreSQL 16-compatible;
- TLS connection string;
- automated backups;
- point-in-time recovery preferred;
- ability to run pg_dump/pg_restore or provider equivalent;
- sufficient connection limit for configured INARENA pool.

## Redis
Requirements:
- Redis 7-compatible;
- pub/sub;
- TLS in production when provider supports it;
- non-authoritative: PostgreSQL/outbox remains source of truth.

## Deployment sequence
1. Provision PostgreSQL.
2. Provision Redis.
3. Configure backend secrets/environment.
4. Deploy backend container.
5. Container runs migrations before Uvicorn.
6. Verify `/ready`.
7. Deploy frontend with `VITE_API_BASE`.
8. Add frontend origin to `INARENA_ALLOWED_ORIGINS`.
9. Run staging smoke/full-stack E2E.
10. Run hosted PostgreSQL backup/restore drill.
11. Configure Telegram Mini App HTTPS URL.
12. Begin real-device dry run.

## Required backend environment
- INARENA_ENV=staging or production
- INARENA_DATABASE_URL
- INARENA_REDIS_URL
- INARENA_OPERATOR_KEY
- INARENA_ALLOWED_ORIGINS
- INARENA_RELEASE
- TELEGRAM_BOT_TOKEN for Telegram auth

## Optional tuning
- INARENA_DB_POOL_MIN
- INARENA_DB_POOL_MAX
- INARENA_DB_POOL_TIMEOUT_SECONDS
- INARENA_RATE_LIMIT_AUTH_PER_MINUTE
- INARENA_RATE_LIMIT_OPERATOR_PER_MINUTE
- INARENA_RATE_LIMIT_PLAYER_PER_MINUTE
- INARENA_RATE_LIMIT_WS_PER_MINUTE
- INARENA_MAX_REQUEST_BODY_BYTES

## Current provider compatibility
The current application architecture is compatible with a managed container platform that can provide:
- Docker/web service;
- managed PostgreSQL;
- managed Redis.

Vercel remains suitable for the frontend, but the realtime backend should remain on a persistent runtime.
Render is a suitable alternative for the full staging stack when connected.
