# INARENA Closed-Beta Triage

## Purpose
Keep the beta freeze intact while reacting quickly to correctness, security and core-flow failures.

## Severity

### P0 — integrity / security
Examples:
- chip conservation violation;
- duplicate ledger movement;
- private-card leakage;
- unauthorized operator/player action;
- corrupted tournament result;
- unrecoverable database/realtime divergence.

Action:
- stop affected beta flow;
- preserve logs/request IDs;
- reproduce with the same release;
- fix before beta resumes.

### P1 — core flow blocked
Examples:
- cannot authenticate;
- cannot register/join/act;
- table stuck;
- reconnect cannot recover;
- operator cannot resolve a blocked table.

Action:
- beta may continue only outside the affected flow;
- blocker fix allowed during feature freeze.

### P2 — degraded / workaround exists
Examples:
- intermittent UI state;
- confusing but recoverable workflow;
- non-critical operator friction.

Action:
- collect evidence;
- fix if repeated or high-frequency.

### P3 — cosmetic / polish
Examples:
- spacing;
- typography;
- non-blocking visual inconsistency.

Action:
- defer to UX polish batch unless unusually disruptive.

## Required evidence
For P0/P1:
- release or commit;
- device/browser/Telegram version;
- exact reproduction steps;
- request ID when available;
- privacy-safe diagnostics payload;
- screenshot or screen recording when useful.

Never paste:
- Telegram initData;
- session IDs;
- operator tokens;
- private hole cards outside approved internal debugging.

## Beta freeze rule
Allowed changes:
- blocker fixes;
- correctness;
- security;
- approved core-flow completion.

New features go to the post-beta backlog.

## Verification
A P0/P1 fix is not closed until:
1. regression test exists when automatable;
2. backend/frontend CI is green on the fix commit;
3. affected dry-run or device flow is repeated;
4. release identifier is recorded in the issue.
