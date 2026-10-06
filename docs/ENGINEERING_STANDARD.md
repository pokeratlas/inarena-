# INARENA Engineering Standard

## Delivery sequence
Every substantial feature moves through:

1. Product definition
2. Domain / state model
3. API contract
4. UX / visual specification
5. Implementation
6. Unit tests
7. Integration tests
8. Visual QA
9. Mobile QA
10. Security review
11. Reconnect / failure testing
12. Load testing where relevant
13. Preview
14. Production release
15. Checkpoint

## Mandatory invariants
- Server-authoritative game state
- Strict action sequencing
- Idempotent player mutations
- Ledger-based chip accounting
- No private-card leakage
- Reconnect must not duplicate actions
- Settled hands never become active again
- Total chips are conserved except explicit ledger entries
- Every operator mutation is auditable

## Tooling
- Figma: source of truth for visual design
- Storybook: component implementation review
- React + TypeScript: client
- FastAPI: current backend baseline
- PostgreSQL: production primary database
- Redis: realtime/cache/coordination layer where needed
- WebSocket: realtime transport
- GitHub Actions: CI
- pytest: backend tests
- Playwright: UI/integration/visual tests
- Hypothesis: rules/property tests
- k6: load testing
- Sentry + OpenTelemetry: observability
- PostHog or equivalent: product analytics

## AI workflow
TASK -> ACCEPTANCE CRITERIA -> IMPLEMENT -> TEST -> REVIEW -> VERIFY -> CHECKPOINT

Large tasks must be split into independently testable units.
