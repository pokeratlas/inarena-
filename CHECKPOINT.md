# INARENA checkpoint

## Source of truth
GitHub repository `pokeratlas/inarena-` is the primary codebase.
The project is cloud-first and does not depend on a specific Windows PC.

## Confirmed product direction
- Master brand: INARENA
- Direction: professional sport × lifestyle
- ONLINE UI: approved Concept 2
- OFFLINE / ONLINE switching changes both main content and bottom navigation.
- ONLINE bottom navigation: Лобби | Игра | Профиль.
- Gameplay uses a dedicated fullscreen table screen.

## Verified backend
Implemented and verified in GitHub Actions:
- SQLite runtime tables, seats and active hands
- schema migrations through v5
- persisted hand results, auth sessions, action log and recovery audit
- secure private-card storage separated from public realtime state
- persisted shuffled deck per active hand
- two private hole cards dealt server-side to every player
- public board progression: preflop → flop → turn → river
- betting-round completion detection
- all-in runout to a complete board when no further betting is possible
- showdown_pending state
- NL Hold'em best-5-of-7 evaluator
- tie detection and deterministic pot split
- protected showdown settlement endpoint
- atomic stack/pot settlement
- monotonic realtime sequence log and reconnect replay
- stale-action protection through expected_action_no
- server-side turn validation
- Telegram Mini App initData verification
- persistent authenticated sessions
- authenticated seat/join flow using X-Session-ID
- authenticated private table view; only the current player receives their hole cards
- authenticated player-action endpoint bound to session identity
- protected operator pause/resume/recovery controls

## Verified frontend
- React + TypeScript + Vite
- Concept 2 mobile shell
- OFFLINE / ONLINE architecture
- live ONLINE lobby
- authenticated “Сесть за стол” flow
- fullscreen live table
- public board cards
- private hole cards loaded through authenticated player view
- Fold / Check / Call / Bet / Raise
- 1/2 Pot / 3/4 Pot / Pot / All-in sizing controls
- sequence-aware WebSocket reconnect/replay
- Telegram Mini App identity bridge
- frontend dependency override pins baseline-browser-mapping 2.11.26 for reproducible CI

## CI
- private cards / street progression / auth seating: PASS
- action sequencing / chip movement: PASS
- showdown evaluator / settlement: PASS
- Telegram auth: PASS
- persistence / reconnect / operator recovery: PASS
- frontend production build: PASS

## Current external blocker
The connected Vercel integration currently returns no accessible Vercel team/account, so a public Vercel preview cannot be published from this session yet.

## Next
1. Add blinds / dealer-button rotation and correct preflop/postflop action order.
2. Add betting minimum-raise rules and all-in side-pot support.
3. Add automatic uncontested-pot settlement.
4. Add hand history and player-visible action log.
5. Polish the live table visual against the approved Concept 2 reference once preview access is available.
