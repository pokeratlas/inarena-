# INARENA Profile V2

## Goal

Turn the Profile tab from a utility card into a player-facing product surface
without inventing unsupported ranking or achievement data.

## Data shown now

- Telegram identity and avatar when available;
- authoritative Player ID with clipboard flow;
- authoritative internal chip balance;
- up to 50 recent player hand-history rows;
- derived, explicitly local history metrics:
  - hands loaded,
  - hands with payout,
  - maximum pot in loaded history,
  - total payouts in loaded history;
- session provider/status.

## Visual hierarchy

1. Player identity hero.
2. Balance card.
3. Compact stats grid.
4. Player ID utility.
5. Recent hand history.
6. Account/session details.

## Constraints

- no fake global win rate, rating, achievements or leaderboard position;
- no operator controls inside player profile;
- no session ID or credentials displayed;
- no horizontal overflow at mobile widths;
- clipboard denial retains manual-copy guidance.

## Follow-up

Future Profile V3 may add achievements, rankings, tournament results and richer
career statistics only after server-side models exist for those concepts.
