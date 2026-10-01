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
- NL Hold'em best-5-of-7 evaluator
- showdown settlement
- player-visible hand history and action log
- monotonic realtime sequence log and reconnect replay
- stale-action protection through expected_action_no
- Telegram Mini App initData verification
- persistent authenticated sessions
- authenticated seating, private view and player actions
- protected operator pause/resume/recovery controls

## Verified frontend
- React + TypeScript + Vite
- Concept 2 mobile shell
- OFFLINE / ONLINE architecture
- live ONLINE lobby
- authenticated seating
- fullscreen live table
- public board and private hole cards
- Fold / Check / Call / Bet / Raise
- 1/2 Pot / 3/4 Pot / Pot / All-in sizing
- D / SB / BB seat badges
- current blind structure and minimum raise display
- last-hand result
- player-visible action log
- sequence-aware WebSocket reconnect/replay
- Telegram Mini App identity bridge
- reproducible frontend dependency pin

## CI
Latest backend CI: PASS.
Latest frontend CI: PASS.
Dedicated NLH rules regression tests: PASS.
Side-pot, min-raise, button rotation, uncontested settlement and hand-history tests: PASS.

## Current external blocker
The connected Vercel integration currently returns no accessible Vercel team/account, so a public Vercel preview cannot be published from this session yet.

## Next
1. Harden production API by disabling unauthenticated legacy join/action routes outside test mode.
2. Add blind-level configuration/operator controls.
3. Add automatic showdown trigger when no player decisions remain.
4. Add reconnect-aware pending-action UX and action timer.
5. Add richer hand-history details and per-player history view.
6. Publish cloud preview when Vercel access becomes available.
