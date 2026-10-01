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
- schema migrations through v8
- cash / tournament table modes
- configurable starting stack
- cash buy-in min/max validation
- cash-out accounting through persistent table ledger
- tournament elimination status at zero stack
- rebuy policy: enabled/disabled, rebuy stack, per-player rebuy limit
- add-on policy and configured add-on stack
- authenticated rebuy / add-on endpoints
- persisted tournament blind schedules
- blind schedule start / pause / reset controls
- automatic blind-level advancement while schedule is running
- operator table configuration API
- enriched operator dashboard metrics and table status
- server-side action deadline policy
- automatic timeout resolution: check when legal, otherwise fold
- automatic timeout resolution from the realtime WebSocket loop
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
- cash/tournament mode and blind level visible in lobby
- tournament seating uses configured starting stack
- authenticated Rebuy / Add-on controls
- authenticated cash-table leave flow
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
- operator dashboard frontend available at `?operator=1`
- operator key entered at runtime and kept in sessionStorage, not embedded in the bundle
- dashboard metrics and tournament blind schedule start/pause/reset controls

## CI
Latest backend CI: PASS.
Latest frontend CI: PASS.
Tournament elimination / rebuy / add-on tests: PASS.
Cash buy-in min/max and cash-out ledger tests: PASS.
Blind schedule start/pause/reset tests: PASS.
Timeout/session/dashboard tests: PASS.
Existing NLH rules/reconnect/security regression suite: PASS.

## Current external blocker
The connected Vercel integration currently returns no accessible Vercel team/account, so a public Vercel preview cannot be published from this session yet.

## Next
1. Add one-time add-on tracking so add-on cannot be repeated indefinitely.
2. Add tournament finishing/ranking state when active players fall to one.
3. Add cash-table balance/account model instead of direct chip-stack buy-in input.
4. Add operator controls for rebuy/add-on windows and table close.
5. Add table-level audit/history view in operator dashboard.
6. Add production deployment configuration and preview when Vercel access is available.
