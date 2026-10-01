# INARENA checkpoint

## Source of truth
GitHub repository `pokeratlas/inarena-` is the primary codebase.
The project is cloud-first and no longer depends on a specific Windows PC.

## Confirmed product direction
- Master brand: INARENA
- Direction: professional sport × lifestyle
- ONLINE UI: approved Concept 2
- OFFLINE / ONLINE switching changes both the main content and bottom navigation.
- ONLINE bottom navigation: Лобби | Игра | Профиль.
- Poker table uses a dedicated fullscreen gameplay screen and hides the bottom navigation.

## Verified backend
Implemented and verified in GitHub Actions:
- SQLite runtime tables, seats and active hands
- persisted hand results and auth sessions
- versioned schema migrations through schema v4
- persisted realtime event log with monotonic sequence IDs
- reconnect replay from `after_seq`
- WebSocket snapshot/replay/event protocol
- atomic hand completion with payout validation and rollback
- protected operator API
- pause / resume
- audited operator hand abort/recovery
- ordered server-side player actions
- expected-action sequence guard against stale/repeated taps
- server-side turn validation
- atomic bet/call chip movement and pot updates
- hand action audit table
- verified Telegram Mini App initData authentication
- persisted Telegram session after successful validation

## Verified frontend
- React + TypeScript + Vite
- approved OFFLINE / ONLINE mode architecture
- ONLINE lobby connected to live API
- fullscreen ONLINE table screen
- sequence-aware WebSocket reconnect
- Telegram Mini App bridge and authenticated player identity
- player actions only shown when it is the authenticated player's turn
- Fold / Check / Call / Bet / Raise
- approved 1/2 Pot / 3/4 Pot / Pot / All-in sizing controls
- Concept 2 cobalt-blue / navy glass visual foundation
- 390–430px mobile-first shell
- safe-area aware layout
- fullscreen table hides bottom navigation

## CI
- backend action sequencing: PASS
- Telegram authentication: PASS
- backend persistence/reconnect/operator/recovery: PASS
- frontend production build: PASS
- Concept 2 shell and sizing controls: PASS

## Current blocker
Vercel connector currently returns no accessible Vercel team/account, so a Vercel cloud preview cannot be published from this session yet.

## Next
1. Add dealt cards / board state and street progression.
2. Add round-completion logic and showdown settlement handoff.
3. Add Telegram-authenticated join/seat flow.
4. Publish cloud preview when Vercel account/team access becomes available.
