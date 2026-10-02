# Hosted PostgreSQL Verification Drill

Run this after selecting the staging/production PostgreSQL provider.

## Inputs
- provider connection URL;
- temporary staging database;
- SSL mode required by provider;
- backup destination with restricted access.

## Procedure
1. Set `INARENA_DATABASE_URL` to the hosted staging database.
2. Run:
   ```bash
   python -m app.migrate upgrade
   python -m app.migrate check
   ```
3. Start the backend and require `/ready` = 200.
4. Seed a meaningful INARENA fixture:
   - one cash table;
   - player balances;
   - one settled hand;
   - ledger rows;
   - operator audit rows.
5. Create a provider-native backup or `pg_dump --format=custom`.
6. Record backup checksum, timestamp and source release id.
7. Restore into a new empty hosted database.
8. Point a verification backend at the restored database.
9. Run `python -m app.migrate check`.
10. Verify seeded tables, hand results, balances, ledger and audit records.
11. Run staging smoke against the restored database.

## Pass criteria
- schema version matches current application;
- row counts match fixture expectations;
- player balances match;
- table ledger sums match;
- settled hand result exists;
- operator audit exists;
- API readiness and smoke tests pass;
- no destructive migration/reset is needed.

## Production rule
Do not consider backup complete until a restore has been verified against the same provider family used for production.
