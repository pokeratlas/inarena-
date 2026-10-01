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
- schema migrations through v6
- persisted hand results, auth sessions, hand actions and recovery audit
- secure private-card storage separated from public realtime state
- persisted shuffled deck per active hand
- server-side hole cards and public board
- preflop → flop → turn → river progression
- small blind / big blind posting
- heads-up blind rules
- dealer button rotation between completed hands
- correct preflop and postflop action order
- minimum raise enforcement
- legal short all-in handling
- contribution ledger
- main-pot / side-pot calculation by contribution tiers
- tie splitting
- automatic uncontested-pot settlement
- automatic showdown settlement when no further action remains
- NL Hold'em best-5-of-7 evaluator
- player-visible hand history and action log
- authenticated per-player hand history with only that player's hole cards
- monotonic realtime sequence log and reconnect replay
- stale-action protection through expected_action_no
- persisted action deadline / timeout metadata
- Telegram Mini App initData verification
- persistent authenticated sessions
- authenticated seating, standing, private view and player actions
- production hardening: legacy mutation endpoints hidden unless INARENA_ENABLE_LEGACY_API=1
- operator-only table creation and hand start
- operator blind-level controls between hands
- protected operator pause/resume/recovery controls

## Verified frontend
- React + TypeScript + Vite
- Concept 2 mobile shell
- OFFLINE / ONLINE architecture
- live ONLINE lobby
- blind level visible in lobby
- authenticated seating
- fullscreen live table
- public board and private hole cards
- Fold / Check / Call / Bet / Raise
- 1/2 Pot / 3/4 Pot / Pot / All-in sizing
- D / SB / BB seat badges
- current blind structure and minimum raise display
- server-backed action countdown
- reconnect state locks player actions until realtime is restored
- pending-action status
- public last-hand result and action log
- authenticated private player history with own hole cards, board, payout and final stack
- sequence-aware WebSocket reconnect/replay
- Telegram Mini App identity bridge
- reproducible frontend dependency pin

## CI
Latest backend CI: PASS.
Latest frontend CI: PASS.
Production hardening tests: PASS.
Authenticated action/private-history tests: PASS.
Blind-level and persisted timer tests: PASS.
NLH rules, side-pot, showdown, reconnect and recovery regression tests: PASS.

## Current external blocker
The connected Vercel integration currently returns no accessible Vercel team/account, so a public Vercel preview cannot be published from this session yet.

## Next
1. Add server-side timeout resolution policy (check when legal, otherwise fold).
2. Add automated blind schedule levels for tournament-style tables.
3. Add table creation/configuration model for cash-style vs tournament-style play.
4. Add player reconnect/session refresh and session expiry enforcement.
5. Add richer operator dashboard data.
6. Publish cloud preview when Vercel access becomes available.
