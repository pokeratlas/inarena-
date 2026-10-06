# Operator Reports / Exports

## Goal
Provide deterministic operational exports for audit, tournament operations and chip-ledger reconciliation.

## Report types

### Table Ledger
Fields:
- table_id
- player_id
- entry_type
- amount
- details
- created_at

### Tournament Results
Fields:
- table_id
- player_id
- seat_no
- finish_place
- stack
- rebuy_count
- addon_used
- eliminated_at
- winner
- finished_at

### Tournament Registrations
Fields:
- table_id
- user_id
- status
- registered_at
- withdrawn_at

### Operator Audit
Fields:
- id
- table_id
- action
- details
- created_at

## Formats
- JSON
- CSV

CSV must:
- use UTF-8;
- have a stable header order;
- serialize nested details as compact JSON strings.

## Security
All report endpoints are operator-authenticated.

## Determinism
Reports are ordered explicitly:
- ledger by id ascending;
- registrations by registered_at then user_id;
- results by finish_place ascending, then seat_no;
- audit by id ascending for exports.

## Non-goals
No monetary accounting is introduced. Chip data remains internal non-monetary game-unit accounting.
