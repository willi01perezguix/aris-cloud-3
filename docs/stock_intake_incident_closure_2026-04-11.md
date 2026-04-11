# Stock intake incident closure note (2026-04-11)

## Main ticket closure summary

Status: **CLOSED**.

Validated scope:
- `save_preload_line` happy path and validation/conflict behavior.
- `assign_pending_epc` happy path and duplicate EPC conflict mapping.
- `release_epc` behavior and EPC reuse behavior.
- `mark_issue` and `resolve_issue` transitions for issue disposition lifecycle.

Code evidence:
- `save_preload_line` writes pending items (`item_status=PENDING_EPC`) when EPC is absent, and writes final RFID+assignment (`item_status=ACTIVE`, `epc_status=ASSIGNED`) when EPC is present, with guarded EPC conflict checks and integrity conflict mapping. 
- `assign_pending_epc` now requires `lifecycle_state=PENDING_EPC` and `saved_stock_item_id`, then updates both preload and live stock records and writes assignment atomically.
- `release_epc` deactivates current assignment and clears live stock EPC while setting `epc_status=AVAILABLE`.
- `mark_issue` with release options releases active assignment and conditionally clears EPC from live stock.
- `resolve_issue` requires current issue state and, when resolving to `ACTIVE`, restores live stock `status` to `RFID` and clears `issue_state`.

Test evidence:
- `test_preload_save_to_epc_final_and_conflict`
- `test_assign_pending_epc_duplicate_returns_conflict_and_new_epc_succeeds`
- `test_epc_release_and_reuse`
- `test_issue_release_then_resolve_restores_stock_status_and_preserves_preload_snapshot`

Conclusion:
- Main incident acceptance path is covered in code and regression tests.
- The historical resolve_issue inconsistency is addressed and tested in the integrated issue lifecycle test.
- Remaining concerns are follow-up contract/design items and are tracked separately below.

## Follow-up ticket 1 (Idempotency-Key contract vs implementation)

- **Title**: Align Idempotency-Key contract and runtime behavior for preload/EPC/issue stock mutations.
- **Problem statement**: Stock mutation endpoints (`save_preload_line`, `assign_pending_epc`, `release_epc`, `mark_issue`, `resolve_issue`) do not currently execute through `IdempotencyService`, but broader architecture docs present idempotency as required/expected for critical mutations.
- **Current evidence**:
  - Router implementations for the five endpoints do not call `extract_idempotency_key` or `IdempotencyService.start`.
  - Generated OpenAPI for these endpoints currently does not include `Idempotency-Key` parameter.
  - Architecture documentation still states broad idempotency requirements for mutating operations.
- **Impact/risk**: Retry storms or client retries can create duplicate mutation attempts without standardized replay behavior; contract drift risks integration confusion.
- **Scope**:
  - Decide contract for these endpoints (required, optional, or explicitly unsupported).
  - Update OpenAPI + docs + middleware/handler behavior consistently.
  - Add integration tests for replay/conflict semantics once contract is chosen.
- **Out of scope**:
  - Refactoring unrelated stock/import routes.
  - Retrofitting idempotency across unrelated domains.
- **Suggested acceptance criteria**:
  - Contract explicitly documented per endpoint.
  - Runtime behavior matches docs and OpenAPI.
  - Replay/conflict cases covered by tests.
- **Suggested tests**:
  - Missing key handling (if required).
  - Same key + same payload replay returns deterministic response.
  - Same key + different payload returns conflict.
- **Suggested owner area**: router + middleware + openapi/docs.
- **Risk level**: Medium.
- **Migration likely required**: No (unless storage/index changes are introduced for route-specific idempotency state).

## Follow-up ticket 2 (item_uid type alignment)

- **Title**: Normalize `item_uid` type alignment across migrations/schema/runtime queries.
- **Problem statement**: Runtime models use UUID/GUID for `item_uid`, but migration history introduced `stock_items.item_uid` as `String(36)`, and several queries cast UUID/string explicitly. This indicates type drift and adapter logic at query time.
- **Current evidence**:
  - `StockItem.item_uid` model type is GUID UUID.
  - Intake migration created `stock_items.item_uid` as string while `preload_lines.item_uid` and `epc_assignments.item_uid` were GUID.
  - Router lookups use `cast(StockItem.item_uid, String) == <item_uid>` in multiple endpoints.
- **Impact/risk**: Type drift increases risk of subtle query/performance/index issues across environments and complicates future joins/contracts.
- **Scope**:
  - Inventory actual DB column types in active environments.
  - Decide canonical DB type for `item_uid`.
  - Remove cast-based compatibility where safely possible after alignment.
  - Update tests for lookup behavior and type assumptions.
- **Out of scope**:
  - Changes to unrelated POS IDs.
  - Broad schema redesign beyond `item_uid` consistency.
- **Suggested acceptance criteria**:
  - `item_uid` canonical type defined and documented.
  - Models, migrations, and runtime queries aligned.
  - No cast workaround needed for standard lookups.
- **Suggested tests**:
  - Regression tests for item lookups across save/assign/release/issue flows.
  - DB-level migration verification test for type and index compatibility.
- **Suggested owner area**: model + migrations + router queries.
- **Risk level**: Medium-High.
- **Migration likely required**: Yes (likely type conversion migration in PostgreSQL environments with string column).

## Follow-up ticket 3 (preload snapshot vs live state contract)

- **Title**: Clarify and document preload snapshot semantics vs live stock lifecycle state.
- **Problem statement**: `preload_lines` currently preserve saved intake snapshot fields and are not synchronized after later live lifecycle changes in `stock_items` and `epc_assignments`. This behavior is visible but not explicitly documented as contract.
- **Current evidence**:
  - `save_preload_line` and `assign_pending_epc` update preload lifecycle fields for intake progression.
  - Subsequent `release_epc` / `mark_issue` / `resolve_issue` update live `stock_items` and assignments, not preload snapshot fields.
  - Regression test asserts preload line remains `SAVED_EPC_FINAL` with original EPC after issue/release/resolve sequence.
- **Impact/risk**: Teams may misinterpret preload API responses as live truth, causing operational confusion and reporting mismatches.
- **Scope**:
  - Document intended semantics in API docs and runbooks.
  - Add explicit field-level guidance: preload snapshot vs live state source of truth.
  - Optionally add response hints/references to live item endpoints (docs only in this ticket).
- **Out of scope**:
  - Implementing data synchronization between preload and live tables.
  - Redesigning preload persistence model.
- **Suggested acceptance criteria**:
  - API/docs explicitly label preload lines as staging/snapshot records.
  - Operational playbook states where to read live item/EPC state.
  - Tests cover and explain intentional divergence.
- **Suggested tests**:
  - Documentation contract test asserting endpoint descriptions mention snapshot/live distinction.
  - Existing integration regression retained for divergence behavior.
- **Suggested owner area**: docs + openapi descriptions + tests.
- **Risk level**: Low.
- **Migration likely required**: No.
