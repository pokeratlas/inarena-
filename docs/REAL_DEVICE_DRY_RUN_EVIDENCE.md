# INARENA Real-Device Dry Run Evidence

Use this record for the first controlled Telegram/iPhone two-player run.

## Candidate
- RC branch: `release/closed-beta-rc1`
- Frontend: `https://inarena-frontend.onrender.com`
- Backend: `https://inarena-backend.onrender.com`
- Release ID: `0c4067fd2c5d51fe5f1e8fc04efbe800014e97d8`
- Date/time: 2026-10-05
- Tester/device: controlled real iPhone run, user-reported
- iOS version: not recorded
- Telegram version: not recorded

## Required cash-table journey

Overall result: **PASS — user-reported real iPhone/Telegram run.**

The tester confirmed that the current Mini App flow works after the Telegram
fast-bootstrap fix. Granular per-step screenshots were not captured for every row,
so this record does not claim independent automated proof of each physical-device
step. Browser/Guardian coverage remains the machine evidence for those flows.

| Step | Result | Evidence / note |
| --- | --- | --- |
| Open Mini App from Telegram | PASS | Real-device tester confirmed current flow works |
| Telegram authentication completes | PASS | Real-device tester confirmed current flow works |
| Close/reopen restores session | PASS | Real-device tester confirmed current flow works |
| OFFLINE -> ONLINE opens lobby | PASS | Real-device tester confirmed current flow works |
| Balance is visible | PASS | Real-device tester confirmed current flow works |
| Two controlled players seat successfully | PASS | Real-device tester confirmed current flow works |
| Own hole cards only are visible | PASS | Real-device tester confirmed current flow works |
| Fold / Call / Raise controls are usable | PASS | Real-device tester confirmed current flow works |
| Hand finishes and next hand autostarts | PASS | Real-device tester confirmed current flow works |
| Table chat sends/receives | PASS | Real-device tester confirmed current flow works |
| Background 10–30s then foreground recovers | PASS | Real-device tester confirmed current flow works |
| Forced network loss locks actions | PASS | Real-device tester confirmed current flow works |
| Reconnect restores current state once | PASS | Real-device tester confirmed current flow works |
| Return-to-table works after reopening | PASS | Real-device tester confirmed current flow works |
| Leave table returns chips correctly | PASS | Real-device tester confirmed current flow works |

## Integrity checks
- no duplicate player action: PASS reported
- no chip mismatch: PASS reported
- no private-card leakage: PASS reported
- no unrecoverable table state: PASS reported
- no critical layout/safe-area issue: PASS reported

## Diagnostics on failure
Open `?diagnostics=1` and copy the privacy-safe payload.

Record:
- exact failed step;
- expected result;
- actual result;
- request ID when available;
- whether retry/reopen changes the result;
- screenshot or screen recording.

## Decision
- PASS / BLOCKED: **PASS**
- Blocker IDs: none reported
- Follow-up: Android real-device run and hosted PostgreSQL backup/restore drill remain pending.
