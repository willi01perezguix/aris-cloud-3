# Stock preload EPC incident closure note (2026-04-11)

## Main ticket closure summary

### What was fixed (verified in current branch)
- EPC duplication handling is guarded both **pre-write** and **commit-time** for preload save/assign:
  - `_assert_epc_available` checks active `epc_assignments` and active `stock_items` conflicts before write.
  - `_commit_preload_epc_write` maps integrity races to `BUSINESS_CONFLICT` with EPC-specific details.
- `save_preload_line` persists correct stock/preload state transitions for both no-EPC (`PENDING_EPC`) and EPC (`SAVED_EPC_FINAL`) paths.
- `assign_pending_epc` now requires prior saved pending state and updates both `preload_lines` and linked `stock_items`, then writes assignment atomically.
- `release_epc` deactivates assignment and clears live EPC from `stock_items`.
- `mark_issue` + `resolve_issue` support issue lifecycle and, for `resolve_issue(item_status="ACTIVE")`, restore `stock_items.status = "RFID"` while clearing `issue_state`.

### What was validated (code + tests)
- End-to-end preload/assign/release/issue/resolve regression is covered in `tests/test_stock_preload_workflow.py`, including:
  - duplicate EPC -> `409 BUSINESS_CONFLICT`;
  - release and EPC reuse;
  - resolve-issue requiring item in issue state;
  - issue release + resolve yielding live state consistency (`status=RFID`, `item_status=ACTIVE`, `epc_status=AVAILABLE`, `epc=None`) and assignment released.

### Why the main incident can be closed
- The previously reported EPC conflict flow and resolve-issue inconsistency are both represented in current route logic and protected by explicit regression tests.
- The historical crossed manual sequence does not indicate a reproducible code-level defect in this branch.

### Explicitly out of scope (left open as follow-ups)
1. Idempotency contract mismatch for preload/save/assign/release/issue endpoints.
2. `item_uid` type alignment across storage/query boundaries.
3. Explicit documentation of `preload_lines` as a saved snapshot vs live stock/assignment state.

---

## Follow-up ticket 1

### Title
Align Idempotency-Key contract with implementation in preload/save/assign/release/issue stock routes

### Problem statement
Some mutating stock routes in this flow do not currently implement `IdempotencyService` protections, while idempotency is implemented for other mutating stock routes (e.g., import/actions). API contract and implementation should be aligned intentionally (either implement or stop advertising/expecting behavior).

### Current evidence from codebase
- `IdempotencyService` is used in `import-epc`, `import-sku`, and bulk `actions` handlers.
- `create_preload_session`, `save_preload_line`, `assign_pending_epc`, `release_epc`, `mark_issue`, `resolve_issue` do not start idempotency contexts.
- In the same router, `openapi_extra` advertises `Idempotency-Key` for SKU image endpoints, which shows mixed idempotency signaling patterns inside stock router.

### Impact / risk
- Retried client writes can create duplicate/non-deterministic side effects where callers assume safe retry semantics.
- Contract ambiguity increases integration incident risk.

### Scope
- Decide route-by-route idempotency policy for preload/save/assign/release/issue.
- Align OpenAPI docs/header exposure with actual behavior.
- Add tests for replay semantics (or explicit non-support behavior).

### Out of scope
- Large transactional redesign of stock lifecycle.
- Non-stock endpoints.

### Suggested acceptance criteria
- Each target endpoint has explicit, tested idempotency behavior.
- OpenAPI and runtime behavior agree.
- Duplicate retries with same key are deterministic where idempotency is supported.

### Suggested tests
- API tests for retry with same `Idempotency-Key` returning replay marker.
- Conflict test for same key + different payload hash.
- Safety tests for endpoints intentionally not idempotent (if chosen) with explicit docs assertions.

### Suggested owner area
router + service + API contract docs/tests

### Risk level
Medium

### Migration likely required later
No (unless persisted idempotency storage schema changes are introduced).

---

## Follow-up ticket 2

### Title
Align item_uid types across preload_lines, stock_items, and epc_assignments

### Problem statement
`item_uid` is modeled as UUID in DB models but several route lookups rely on string casting in SQL filters and string payload fields, indicating type-boundary inconsistency that can affect query plans, constraints, and portability.

### Current evidence from codebase
- Models define UUID-like `item_uid` in `preload_lines`, `stock_items`, `epc_assignments`.
- Runtime queries frequently use `cast(..., String) == <string item_uid>` (e.g., stock lookup and issue flows).
- `EpcReleaseRequest.item_uid` schema is `str`, and release query compares assignment UUID column directly to payload string while stock lookup uses cast-to-string fallback.
- Regression test exists specifically for release working with string `item_uid` lookup.

### Impact / risk
- Inconsistent typing increases risk of subtle mismatches and DB-specific behavior drift.
- Casted predicates can reduce index efficiency and complicate future migrations.

### Scope
- Define canonical API type for `item_uid` (UUID string externally, UUID internally).
- Remove ad-hoc casting where possible through normalized parsing/validation.
- Ensure consistent comparisons across preload/stock/assignment tables.

### Out of scope
- Full schema redesign beyond `item_uid` handling.
- Broad unrelated query tuning.

### Suggested acceptance criteria
- All affected route inputs validate/normalize `item_uid` consistently.
- DB predicates use type-consistent UUID comparisons.
- Existing workflows (save/assign/release/issue/resolve) remain behaviorally unchanged.

### Suggested tests
- UUID and non-UUID payload validation tests.
- Release/issue lookup tests proving no cast-to-string dependency.
- Query-path regression tests for cross-table `item_uid` consistency.

### Suggested owner area
model + schema + router + tests

### Risk level
Medium-High

### Migration likely required later
Possibly (if current physical column types differ across environments or require backfill/standardization).

---

## Follow-up ticket 3

### Title
Document preload_lines as saved snapshot vs live state in stock_items and epc_assignments

### Problem statement
Current behavior preserves preload line values as an ingestion/saved snapshot, while live EPC/item lifecycle state evolves in `stock_items` and `epc_assignments`. This is behaviorally correct in tests but not clearly documented for operators/integrators.

### Current evidence from codebase
- `save_preload_line` writes `stock_items` and may mutate preload line lifecycle fields.
- Later operations (`release_epc`, `mark_issue`, `resolve_issue`) update live tables, but preload line fields are not synchronized back to current live EPC state.
- Regression test explicitly asserts preload snapshot EPC remains while live item EPC becomes null after issue+release+resolve.

### Impact / risk
- Without documentation, users may interpret preload session readbacks as authoritative live stock state.
- Incident triage confusion and false positives in manual verification.

### Scope
- Document source-of-truth boundaries for preload sessions vs live stock/assignment.
- Add API docs/runbook notes for operators and QA.
- Clarify expected post-release/issue read models.

### Out of scope
- Data model changes to synchronize snapshot and live state.
- API behavior changes.

### Suggested acceptance criteria
- Docs clearly define snapshot vs live tables and intended use.
- QA runbook includes verification sequence and expected states.
- Support playbook references authoritative endpoint/table for live status.

### Suggested tests
- Documentation-only ticket: no code behavior change required.
- Optional contract test asserting existing snapshot/live divergence behavior remains intentional.

### Suggested owner area
docs + router docstrings/OpenAPI descriptions

### Risk level
Low

### Migration likely required later
No.
