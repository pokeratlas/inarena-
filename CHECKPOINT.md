# INARENA checkpoint

## Source of truth
GitHub repository `pokeratlas/inarena-` is the primary codebase.
The project is cloud-first and no longer depends on a specific Windows PC.

## Confirmed product direction
- Master brand: INARENA
- Direction: professional sport × lifestyle
- ONLINE UI direction: Concept 2
- OFFLINE / ONLINE switching changes both the main content and bottom navigation.
- Work continues from the INARENA checkpoint, not from NARQ.

## Verified backend
Implemented and verified in GitHub Actions:
- SQLite-backed runtime tables, seats and active hands
- persisted hand results and auth sessions
- versioned schema migrations through schema v3
- persisted realtime event log with monotonic sequence IDs
- reconnect replay from `after_seq`
- WebSocket snapshot/replay/event protocol
- atomic hand completion with payout validation and rollback
- Telegram/email-compatible session persistence
- protected operator API
- pause / resume
- audited operator hand abort/recovery
- recovery requires paused state
- realtime event emitted after operator recovery

## Verified frontend cloud baseline
- React + TypeScript + Vite
- OFFLINE / ONLINE application mode architecture
- different bottom navigation sets per mode
- ONLINE lobby data client
- live table list
- selected table state
- sequence-aware WebSocket reconnect hook
- replay support after lost connection
- frontend build CI

The visual layer remains intentionally minimal so the approved ONLINE Concept 2 can be applied without changing the underlying behavior.

## CI
- backend persistence/reconnect: PASS
- atomic settlement/session persistence: PASS
- operator controls/recovery: PASS
- schema migration/realtime replay: PASS
- frontend production build: PASS

## Next
1. Apply the approved Concept 2 visual system to the cloud frontend.
2. Build the ONLINE table screen on top of the realtime state hook.
3. Add player actions and server-side action sequencing.
4. Connect Telegram identity flow to persisted sessions.
5. Configure cloud preview/deployment.
