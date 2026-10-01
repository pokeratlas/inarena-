# INARENA checkpoint

## Source of truth
GitHub repository `pokeratlas/inarena-` is now the primary codebase.

## Confirmed product direction
- Master brand: INARENA
- Direction: professional sport × lifestyle
- ONLINE UI direction: Concept 2
- Work must continue from the current product checkpoint, not from NARQ.

## Current engineering stage
Cloud baseline created for the ONLINE live-table runtime.

Implemented in this baseline:
- SQLite-backed `runtime_tables`
- SQLite-backed `runtime_seats`
- SQLite-backed `active_hands`
- `auth_sessions` schema
- table create/list/read
- join / stand
- start-hand / complete-hand
- WebSocket reconnect snapshot
- restart recovery from persisted active-hand state
- CI tests for persistence and reconnect

## Next
1. Make hand completion fully atomic with stack/pot settlement data.
2. Persist Telegram/auth sessions through an explicit service/API.
3. Add recovery invariants and migration/versioning.
4. Expand realtime event sequencing.
5. Admin/operator controls.
