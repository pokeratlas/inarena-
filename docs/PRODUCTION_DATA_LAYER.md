# INARENA Production Data Layer

## Goal
Move the production platform from the SQLite development baseline to a persistent PostgreSQL-backed runtime without changing poker-domain behavior.

## Migration strategy

### Phase 1 — Database boundary
Introduce a database adapter behind the existing service layer.

Responsibilities:
- connection lifecycle;
- transaction lifecycle;
- row mapping;
- migration execution;
- backend capability detection.

Domain services must not depend directly on SQLite-only PRAGMA behavior.

### Phase 2 — PostgreSQL schema parity
Recreate the verified schema in PostgreSQL with equivalent constraints for:
- tables / seats;
- active hands;
- hand history;
- private cards;
- sessions;
- ledger;
- waitlist / reservations;
- idempotency command journal;
- realtime outbox;
- operator audit;
- tournament registration.

### Phase 3 — Integration CI
Run the complete backend regression suite against:
- SQLite development adapter;
- PostgreSQL integration database.

A feature is not production-ready until both suites pass.

### Phase 4 — Redis coordination
Redis is not the accounting source of truth.

Use Redis only for:
- WebSocket instance coordination;
- ephemeral presence;
- short-lived locks where PostgreSQL locking is insufficient;
- pub/sub between backend instances;
- rate limiting.

Authoritative poker, ledger and tournament state remains PostgreSQL.

## PostgreSQL transaction requirements
Critical operations must stay atomic:
- balance debit + cash seat creation + ledger entry;
- cash-out + balance credit + ledger entry;
- betting mutation + hand action + final outbox event;
- showdown settlement + hand result + seat stacks;
- reservation claim + balance debit + seat + ledger;
- idempotency state transitions coupled to business command resolution.

## Connection pooling
Production backend uses a bounded pool.
Connection limits must be configurable by environment.

## Migration tooling
Target: Alembic or an equivalent explicit migration runner.

Migrations are:
- immutable once released;
- ordered;
- tested on empty database;
- tested upgrading a prior schema snapshot.

## Backup / restore
Production requirements:
- automated PostgreSQL backups;
- point-in-time recovery where hosting supports it;
- documented restore test;
- backup retention policy;
- pre-release backup before schema migrations.

## Staging
Staging must use the same database engine as production.
SQLite remains permitted for local fast tests only.

## Redis failure behavior
Loss of Redis may degrade realtime coordination but must not:
- lose chips;
- corrupt a hand;
- permit duplicate settlement;
- invalidate the PostgreSQL source of truth.
