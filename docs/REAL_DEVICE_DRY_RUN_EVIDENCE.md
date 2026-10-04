# INARENA Real-Device Dry Run Evidence

Use this record for the first controlled Telegram/iPhone two-player run.

## Candidate
- RC branch: `release/closed-beta-rc1`
- Frontend: `https://inarena-frontend.onrender.com`
- Backend: `https://inarena-backend.onrender.com`
- Release ID: record from `?diagnostics=1`
- Date/time:
- Tester/device:
- iOS version:
- Telegram version:

## Required cash-table journey

Record PASS / FAIL and attach a screenshot or screen recording for failures.

| Step | Result | Evidence / note |
| --- | --- | --- |
| Open Mini App from Telegram |  |  |
| Telegram authentication completes |  |  |
| Close/reopen restores session |  |  |
| OFFLINE -> ONLINE opens lobby |  |  |
| Balance is visible |  |  |
| Two controlled players seat successfully |  |  |
| Own hole cards only are visible |  |  |
| Fold / Call / Raise controls are usable |  |  |
| Hand finishes and next hand autostarts |  |  |
| Table chat sends/receives |  |  |
| Background 10–30s then foreground recovers |  |  |
| Forced network loss locks actions |  |  |
| Reconnect restores current state once |  |  |
| Return-to-table works after reopening |  |  |
| Leave table returns chips correctly |  |  |

## Integrity checks
- no duplicate player action:
- no chip mismatch:
- no private-card leakage:
- no unrecoverable table state:
- no critical layout/safe-area issue:

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
- PASS / BLOCKED:
- Blocker IDs:
- Follow-up:
