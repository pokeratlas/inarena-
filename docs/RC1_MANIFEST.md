# INARENA Closed Beta RC1

## Frozen release
- Branch: `release/closed-beta-rc1`
- Commit: `3761901c4ceff48d6cd187308e8e50cf144753a6`
- Purpose: public HTTPS staging + real Telegram device dry run + hosted PostgreSQL restore drill.

## Verified CI on frozen commit
- Backend CI: PASS
  - Run: 37050247734
- Frontend CI: PASS
  - Run: 37050247869

The release line includes:
- PostgreSQL migrations and bounded pool;
- Redis realtime coordination;
- transactional outbox;
- crash-safe idempotency;
- NL Hold'em ruleset;
- cash/tournament lifecycle;
- scoped operator sessions;
- production security perimeter;
- observability/request IDs;
- property-based poker invariants;
- Playwright browser/full-stack gates;
- k6 load baseline;
- Docker production build;
- Render staging Blueprint;
- backup/restore and deployment runbooks.

## Beta freeze policy
Allowed changes on the release candidate:
- P0 integrity/security fixes;
- P1 core-flow blocker fixes;
- compatibility fixes required by the selected hosting provider;
- fixes discovered by iPhone/Android Telegram dry run;
- fixes discovered by hosted backup/restore drill.

Not allowed:
- new game features;
- new navigation areas;
- new tournament/cash policy features;
- cosmetic redesign unrelated to a beta blocker.

## Remaining external gates
1. Provision public HTTPS staging from `render.yaml`.
2. Supply runtime secrets:
   - `INARENA_OPERATOR_KEY`
   - `TELEGRAM_BOT_TOKEN`
3. Verify public `/ready` and `/version`.
4. Run public staging smoke/full-stack flow.
5. Configure Telegram Mini App to the staging frontend URL.
6. Complete iPhone + Android dry run.
7. Complete hosted PostgreSQL backup/restore drill.
8. Record outcomes and release request IDs in beta evidence.

## Promotion rule
RC1 may be promoted to closed beta only when all remaining external gates are PASS and no P0/P1 blocker is open.
