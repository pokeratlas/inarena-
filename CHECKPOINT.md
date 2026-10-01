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
- schema migrations through v7
- cash / tournament table modes
- configurable starting stack
- persisted tournament blind schedules
- automatic blind-level advancement between hands
- operator table configuration API
- operator dashboard summary
- server-side action deadline policy
- automatic timeout resolution over realtime loop: check when legal, otherwise fold
- manual protected timeout-resolution endpoint retained for recovery
- session TTL enforcement with 401 on expiry
- authenticated session restore / refresh
- tournament joins force configured starting stack
- production legacy API hardening
- operator-only table lifecycle
- authenticated seating, standing, private view and player actions
- full NL Hold'em blind/button/action-order/min-raise/side-pot/showdown ruleset
- automatic uncontested and showdown settlement
- public and authenticated per-player hand history
- monotonic realtime sequence log and reconnect replay
- protected operator pause/resume/recovery controls

## Verified frontend
- React + TypeScript + Vite
- Concept 2 mobile shell
- OFFLINE / ONLINE architecture
- live ONLINE lobby
- cash/tournament mode visible in lobby
- configured blind level visible in lobby
- tournament seating uses configured starting stack
- Telegram session restore from local storage
- session validation and refresh on app reopen
- fullscreen live table
- D / SB / BB badges
- board and authenticated private hole cards
- action timer driven by persisted server deadline
- reconnect locks actions until realtime is restored
- Fold / Check / Call / Bet / Raise
- 1/2 Pot / 3/4 Pot / Pot / All-in sizing
- public last-hand action log
- authenticated private hand history

## CI
Latest backend CI: PASS.
Latest frontend CI: PASS.
Automatic timeout resolution test: PASS.
Tournament blind schedule test: PASS.
Session expiry/refresh test: PASS.
Tournament starting-stack enforcement test: PASS.
Operator dashboard test: PASS.
Existing NLH rules/reconnect/security regression suite: PASS.

## Current external blocker
The connected Vercel integration currently returns no accessible Vercel team/account, so a public Vercel preview cannot be published from this session yet.

## Next
1. Add automatic tournament elimination / active-player status.
2. Add rebuy/add-on policy model for tournament mode.
3. Add cash-table buy-in min/max and leave-table stack accounting.
4. Add operator controls for schedule start/pause/reset.
5. Add operator dashboard frontend.
6. Add production deployment configuration and preview when Vercel access is available.
