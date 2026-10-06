# Hosted PostgreSQL Backup / Restore Drill

## Goal
Verify that the selected staging PostgreSQL provider can recover INARENA data before closed beta.

## Preconditions
- public staging backend is healthy;
- database migrations are current;
- at least one test table/hand/history record exists;
- a disposable restore database is available.

## Backup
Create a provider backup or logical dump.

For a logical dump:

```bash
pg_dump --format=custom --no-owner --no-acl \
  "$INARENA_DATABASE_URL" \
  > inarena-staging-drill.dump
```

Record:
- UTC timestamp;
- release SHA from `/version`;
- schema version from `/ready`;
- dump checksum;
- source database identifier.

## Verify dump structure

```bash
pg_restore --list inarena-staging-drill.dump > /dev/null
sha256sum inarena-staging-drill.dump
```

## Restore
Restore only into an isolated database:

```bash
pg_restore --clean --if-exists --no-owner --no-acl \
  --dbname="$INARENA_RESTORE_TEST_URL" \
  inarena-staging-drill.dump
```

Point a temporary backend instance or local migration CLI at the restored database.

Run:

```bash
python -m app.migrate check
```

Verify:
- schema version matches;
- tables/seats/hand history counts match expected fixture values;
- table ledger entries are present;
- operator audit entries are present;
- no active-hand corruption;
- `/ready` succeeds when the restored database is used.

## Pass criteria
The drill is PASS only when:
- dump is readable;
- restore completes without destructive intervention;
- migration check reports up-to-date;
- known test data matches;
- backend readiness succeeds;
- a sample table/history read succeeds.

## Safety
Never run `--clean` against live staging/production.
Never overwrite the source database during the drill.
