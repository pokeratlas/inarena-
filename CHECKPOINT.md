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
- schema migrations through v9
- cash / tournament table modes
- internal non-monetary player chip balance model
- operator balance adjustment with audit
- production cash buy-in debits player chip balance atomically
- authenticated cash-out credits player chip balance atomically
- cash buy-in min/max validation
- persistent cash/table ledger
- tournament elimination at zero stack
- finish-place tracking after rebuy window closes
- tournament winner / finished state
- rebuy window open/close controls
- add-on window open/close controls
- per-player rebuy limits
- one-time add-on enforcement
- operator table close
- closed tables reject new joins / new hands
- operator audit log
- persisted tournament blind schedules
- blind schedule start / pause / reset
- automatic blind-level advancement while running
- server-side action timeout policy and automatic realtime timeout resolution
- session TTL / validation / refresh
- production legacy mutation API hardening
- operator-only table lifecycle
- authenticated seating, standing, private view and player actions
- full NL Hold'em blind/button/action-order/min-raise/side-pot/showdown ruleset
- automatic uncontested and showdown settlement
- public and authenticated per-player hand history
- monotonic realtime sequence log and reconnect replay

## Verified frontend
- React + TypeScript + Vite
- Concept 2 mobile shell
- live ONLINE lobby
- internal chip balance displayed to authenticated player
- cash buy-in button respects configured min/max and available chip balance
- tournament finish places and winner state
- authenticated Rebuy / one-time Add-on controls
- controls respect rebuy/add-on windows
- authenticated cash-table leave / cash-out flow
- Telegram session restore / refresh
- fullscreen live table with D / SB / BB, board and private cards
- server-backed action timer and reconnect lock
- public and private hand history
- operator dashboard at `?operator=1`
- operator chip-balance adjustment
- blind schedule controls
- rebuy/add-on window controls
- table close control
- operator audit log
- operator key remains runtime-only in sessionStorage

## CI
Latest backend CI: PASS.
Latest frontend CI: PASS.
Schema v9 tests: PASS.
One-time add-on tests: PASS.
Tournament finish-place / winner tests: PASS.
Production cash balance debit/credit tests: PASS.
Table-close / operator-audit tests: PASS.
Existing NLH rules, timeout, reconnect, session, side-pot and security regression suite: PASS.

## Current external blocker
The connected Vercel integration currently returns no accessible Vercel team/account, so a public Vercel preview cannot be published from this session yet.

## Next
1. Add tournament registration lifecycle and late-registration cutoff.
2. Add tournament status model: scheduled / registering / running / finished / cancelled.
3. Add cash-table waitlist and seat reservation timeout.
4. Add idempotency keys for all player mutation endpoints.
5. Add operator export/report endpoints for tables, tournament results and chip ledger.
6. Add deployment configuration / persistent production database and publish preview when hosting access is available.
