# INARENA Internal Dry Run Results

## Automated cash-table dry run
Scenario:
- 6 controlled players
- one complete NL Hold'em hand
- preflop call sequence
- check-down through flop / turn / river
- automatic showdown settlement

Verified:
- action order completes without manual intervention;
- board progression reaches five cards;
- hand settles automatically;
- no active hand remains;
- chip conservation holds across all six players;
- hand history is persisted;
- action history is persisted;
- payout total equals final pot.

Result: PASS.

## Automated tournament dry run
Scenario:
- tournament table configured;
- lifecycle configured;
- registration opened;
- 4 controlled players registered;
- all four seated with configured starting stack;
- rebuy window closed;
- tournament started;
- deterministic all-in showdown;
- winner and finish places calculated.

Verified:
- scheduled/registering/running lifecycle;
- registration and seating;
- configured tournament stack;
- rebuy-window close;
- automatic elimination at zero stack;
- finish places 1–4;
- winner_player_id;
- finished_at;
- tournament_status=finished;
- tournament results report.

Result: PASS.

## Infrastructure gates on the same release line
- backend suite: PASS
- property-based poker invariants: PASS
- PostgreSQL: PASS
- Redis: PASS
- staging smoke: PASS
- k6 load baseline: PASS
- production container build: PASS
- frontend build: PASS
- Playwright shell/browser tests: PASS
- full-stack Playwright operator/player flow: PASS

## What this does not replace
Automated dry runs do not replace:
- real Telegram Mini App testing on iPhone/Android;
- multi-device reconnect testing over unstable mobile networks;
- human UX review;
- real operator timing during a tournament;
- backup/restore drill against the actual hosting provider;
- invited-user closed beta.
