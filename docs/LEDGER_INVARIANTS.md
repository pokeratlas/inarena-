# Ledger Invariants

INARENA chips are internal non-monetary game units.

## Sources of truth
- `player_balances`: off-table player chip balance.
- `runtime_seats.stack`: chips currently committed to a table.
- `active_hands.pot`: chips committed to the current hand.
- `table_ledger`: buy-in, cash-out, rebuy and add-on audit trail.
- `operator_audit`: privileged operational mutations.

## Core conservation rule
For operations without an explicit balance adjustment:

`off_table_balance + table_stacks + active_pots`

must remain conserved across the transaction.

## Cash buy-in
Atomic:
1. validate configured min/max;
2. validate available player balance;
3. debit off-table balance;
4. create seat stack;
5. write ledger entry.

No partial state is allowed.

## Cash-out
Atomic:
1. verify no active hand;
2. read seat stack;
3. credit off-table balance;
4. write cash-out ledger entry;
5. remove seat.

## Tournament chips
Tournament starting stacks, rebuys and add-ons are tournament-scoped chips.
They do not debit the cash-table player balance.

## Operator adjustment
Every operator balance adjustment must:
- be authenticated;
- never create a negative balance;
- write an operator audit event.

## Idempotency target
All player mutations that move chips must support an idempotency key before public production release.
