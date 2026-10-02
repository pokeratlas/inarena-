# INARENA PostgreSQL Backup / Restore Runbook

## Scope
This runbook applies to staging and production PostgreSQL. SQLite remains a local-development baseline only.

## Backup
Use the hosting provider's managed backups when available. In addition, before every production schema migration create an explicit logical backup.

Example:

```bash
pg_dump --format=custom --no-owner --no-acl "$INARENA_DATABASE_URL" > inarena-before-migration.dump
```

Record:
- UTC timestamp;
- application release/commit;
- current schema version;
- backup storage location;
- backup checksum.

## Verify backup
A backup is not considered valid until it can be listed:

```bash
pg_restore --list inarena-before-migration.dump > /dev/null
```

## Restore test
Restore into an isolated database, never directly over production:

```bash
createdb inarena_restore_test
pg_restore --clean --if-exists --no-owner --no-acl   --dbname="$INARENA_RESTORE_TEST_URL" inarena-before-migration.dump
```

Then run:
- `python -m app.migrate`;
- `/ready`;
- backend smoke tests;
- chip conservation / ledger sanity checks.

## Production restore
1. Stop write traffic.
2. Preserve the damaged database for forensic analysis.
3. Provision a clean PostgreSQL database.
4. Restore the selected verified backup.
5. Run `python -m app.migrate`.
6. Validate `/ready`.
7. Run smoke tests.
8. Resume traffic only after operator sign-off.

## Retention
Recommended minimum:
- daily backups: 14 days;
- weekly backups: 8 weeks;
- pre-migration backups: retain through at least two successful releases.

Provider point-in-time recovery should be enabled where available.
