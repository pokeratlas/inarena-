# INARENA Architecture

## Bounded contexts

### Identity
Telegram identity, sessions, profile linkage and permissions.

### Poker Runtime
Tables, seats, hands, betting, blinds, board, side pots, timeout, showdown and settlement.

### Tournament
Registration, late registration, blind schedule, rebuy/add-on policy, elimination and ranking.

### Ledger
Internal non-monetary chip balances, buy-ins, cash-outs, adjustments and audit trail.

### Club
Offline tournament and club management.

### Ranking
Player results, series points, achievements and INARENA rankings.

### Operator
Operational controls, recovery, audit, reports and observability.

## State ownership
- Frontend renders and requests actions.
- Backend validates and mutates authoritative state.
- Realtime events communicate changes.
- Persistent storage is the recovery source.
- Ledger entries are the accounting source of truth.

## Production target
Frontend:
- Vercel / equivalent edge hosting

Stateful backend:
- persistent container/runtime
- PostgreSQL
- Redis
- WebSocket support

Storage:
- object storage for media/assets

Observability:
- structured logs
- traces
- metrics
- error monitoring

## Current transition
The current SQLite implementation remains a development baseline.
Production migration target is PostgreSQL before public release.
