# Release integration checkpoint

The owner-approved INARENA target is pokeratlas/inarena-,
release/closed-beta-rc1 at 7908ba7d4326cca39824826838c8903ff10663fd.
The isolated integration branch is integration/shared-core-0.2.2.
Rollback tag: rollback/shared-core-base-7908ba7, at the exact source commit.
No push, merge, deploy, default-branch change or original-tree migration.

STEP 1–3 remain DONE at the accepted core baseline. STEP 4: local A–G gate
passed for the documented SQLite/offline fixture scope. Each layer: 32
release tests PASS, 18/18 conformance scenarios, transaction crash rollback,
fresh-process restart, persisted raise-right, stale request rejection,
receipt replay/no double credit, payload conflict and exact settlement.
Reopening is fixed in consumer rule/state handling, not suppressed by an
adapter. Native engines remain in the source commit; payout shadow checks
raise on semantic mismatch. Five rejection-text differences are explicit
POLICY DIFFERENCE records. Existing gross-refund and inactive wager display
policies remain explicitly documented by the conformance baseline.

STEP 5: DONE for the bounded 0.3.0 product contracts, 96 PASS retained.
STEP 6: isolated decision package DONE; original/real-agent migration
PARTIAL. 40/40 mechanics cases, 5 consumer tests, pinned research metadata.
STEP 7: LOCATION_UNRESOLVED / SOURCE CODE NOT YET LOCATED. NARQ is not
the Anti-Bot source. This does not block other local work.
STEP 8: local documentation/identity proposal DONE; external release/sync
PARTIAL and intentionally not performed.

Production status remains CANDIDATE. PostgreSQL/concurrency, real client
reconnect, production operational scope and approved immutable Shared Core
release identity remain outside this local SQLite gate. Local new-hand
selection must not silently switch legacy active hands.

Owner decisions: approve Shared Core and Intelligence repository/author/
release identities; assign canonical LAB release repository and real-agent
acceptance scope; assign/create Anti-Bot source root; approve operational
acceptance criteria before any production adoption. INARENA target identity
is resolved and must not be requested again.

Do not archive original LAB/INARENA trees, old engines, SAFE snapshot,
Shared Core, Intelligence or either consumer candidate. Temporary recreated
conformance runtimes may be archived only after their evidence/manifests
are retained. No deletion has been performed.

FINAL TESTS: 56 PASS, zero FAIL/ERROR/XFAIL/SKIP. Nine staged gates each repeat the same 32-test release set; do not count those as distinct tests. Final conformance 18/18, fresh release evaluator 1000 comparisons / 0 mismatches. Core baseline 207 and Intelligence 96 retained without STEP 1–3 rerun. Full integration bundle applies to exact rollback commit and reverses to a clean checkout.
