# INARENA checkpoint

## Source of truth
GitHub repository `pokeratlas/inarena-` is the primary codebase.
The project is now cloud-first and no longer depends on a specific Windows PC.

## Confirmed product direction
- Master brand: INARENA
- Direction: professional sport × lifestyle
- ONLINE UI direction: Concept 2
- Work continues from the INARENA checkpoint, not from NARQ.

## Verified backend baseline
Implemented and verified in GitHub Actions:
- SQLite-backed `runtime_tables`
- SQLite-backed `runtime_seats`
- SQLite-backed `active_hands`
- persisted `hand_results`
- persisted `auth_sessions`
- table create/list/read
- join / stand
- start-hand
- persisted pot state
- atomic hand completion with payout validation and stack settlement
- rollback on invalid settlement
- restart recovery of tables, seats and active hands
- Telegram/email-compatible session persistence
- WebSocket reconnect snapshot
- protected operator API using `X-Operator-Key`
- operator table listing
- operator pause / resume with realtime broadcast

## CI
Latest operator-control test run: PASS.
Atomic settlement/session test run: PASS.
Baseline persistence/reconnect test run: PASS.

## Next
1. Add schema migration/version tracking.
2. Add monotonic realtime event sequence IDs and reconnect-from-sequence support.
3. Add operator hand inspection / controlled recovery actions.
4. Start cloud frontend integration with ONLINE Concept 2.
