# Owner Quick Credit v1

A bounded owner convenience built on the existing audited operator balance mutation.

## Scope

- Quick-credit card in Table Manager with Player ID input.
- Positive test-chip presets: +1,000 / +5,000 / +10,000.
- Visible confirmation of the resulting player balance.
- Existing manual delta control remains available under admin tools for advanced corrections.
- Table status filters: All, Live, Open, Paused and Closed.
- No new balance endpoint, ledger semantics, roles, schema or club-management layer.

Player ID is copied from the authenticated player profile. Quick credit uses the
same `operatorAdjustBalance` path that already prevents negative balances and writes
an operator audit entry. Chips remain internal test currency with no deposit or
withdrawal semantics.

## Guardian acceptance

`@guardian-owner-credit` is required on desktop and mobile. It verifies that the
owner can credit a real test session through the UI, that the player balance changes
authoritatively, that relevant controls are usable, and that status filters actually
separate paused and open tables.
