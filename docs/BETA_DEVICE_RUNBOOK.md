# INARENA Telegram Mini App Device Runbook

## Goal
Validate the current release candidate on real iPhone and Android devices before closed beta.

## Required environment
- public HTTPS frontend URL;
- public HTTPS backend URL;
- Telegram bot configured with the Mini App URL;
- production-like PostgreSQL;
- Redis enabled when running multiple backend instances;
- release identifier exposed by /version.

## Device matrix
Minimum:
- iPhone on current supported iOS;
- Android phone on current supported Android;
- portrait orientation;
- Telegram light/dark theme if both are supported by the product shell.

## Player flow
1. Open the Mini App from Telegram.
2. Verify Telegram authentication completes without manual refresh.
3. Confirm player session persists after closing/reopening the Mini App.
4. Switch OFFLINE -> ONLINE.
5. Verify lobby loads without horizontal overflow.
6. Verify chip balance.
7. Join a cash table.
8. Confirm reserved/private data is visible only to that player.
9. Play a controlled hand.
10. Background Telegram for 10–30 seconds.
11. Return and verify realtime reconnect/state replay.
12. Force network loss and recovery.
13. Leave the cash table and verify chip balance returns correctly.
14. Repeat with tournament registration and seating.

## Table UX
Validate:
- 2 / 6 / 9-seat layouts;
- long player names;
- D / SB / BB badges;
- board/hole cards;
- action controls;
- timer;
- reconnect state;
- expired-session state;
- safe areas around Telegram chrome and device notches.

## Failure capture
For every blocker record:
- release id;
- device / OS;
- Telegram version;
- exact flow step;
- expected result;
- actual result;
- screenshot or screen recording;
- request ID when visible;
- whether retry/reopen fixes it.

## Exit criteria
Closed beta may start when:
- no critical authentication/session blocker exists;
- no chip-accounting discrepancy exists;
- no private-card leakage exists;
- reconnect never duplicates player actions;
- no critical mobile layout issue exists at tested widths/devices;
- one complete cash flow and one complete tournament flow pass on both platforms.
