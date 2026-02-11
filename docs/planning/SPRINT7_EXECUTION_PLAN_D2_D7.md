# Sprint 7 Execution Plan (Day 2 to Day 7)

## Day 2 — Python SDK hardening
- **Objective**: Lock SDK behavior to frozen ARIS contract and improve reliability for app-track consumers.
- **Concrete deliverables**:
  - Typed client refinements for stock/import/migrate/POS critical methods.
  - Idempotency envelope helpers for critical mutation calls.
  - Contract-safe examples in SDK docs.
- **Test gates**:
  - SDK unit/integration tests for response shape compatibility.
  - Contract safety script run in strict mode.
- **Done means**:
  - SDK exposes stable interfaces for Day 3+ integrations.
  - All SDK-critical tests pass in CI.
- **Rollback/containment note if blocked**:
  - Freeze SDK API surface to last known good tag and continue app work against pinned version.

## Day 3 — ARIS-CORE-3 app shell (auth/me + effective permissions)
- **Objective**: Deliver a secure app shell with identity and permission context.
- **Concrete deliverables**:
  - Auth bootstrap and `/me` hydration.
  - Effective permissions retrieval and route gating.
  - DENY-first default rendering path.
- **Test gates**:
  - Auth smoke tests (valid/invalid token scenarios).
  - Permission matrix checks for key routes.
- **Done means**:
  - App loads authenticated shell and correctly gates protected views.
- **Rollback/containment note if blocked**:
  - Ship shell in read-only mode with explicit feature flags for blocked routes.

## Day 4 — Stock/Imports/Migrate integration
- **Objective**: Complete inventory workflows in ARIS-CORE-3 with contract-safe behavior.
- **Concrete deliverables**:
  - Full-table stock screen (meta/rows/totals aware).
  - Import EPC/SKU and migrate SKU->EPC execution flows.
  - Error surfaces with trace context.
- **Test gates**:
  - Integration tests covering stock listing and import/migrate happy/guard paths.
  - Totals invariant checks (`TOTAL = RFID + PENDING` in sellable locations).
- **Done means**:
  - Operators can complete stock lifecycle workflows without contract deviations.
- **Rollback/containment note if blocked**:
  - Keep stock read-only enabled; restrict write flows behind kill switch.

## Day 5 — POS Sales + POS Cash integration
- **Objective**: Deliver transaction-safe checkout and cash operations.
- **Concrete deliverables**:
  - POS sales flows (create/update/checkout/return paths as applicable).
  - POS cash session/day-close interactions.
  - UI safeguards for required mutation keys and state transitions via `/actions`.
- **Test gates**:
  - POS smoke scenarios for EPC and SKU sale behavior.
  - Replay/idempotency checks for critical mutation endpoints.
- **Done means**:
  - End-to-end POS path works with invariant-safe stock outcomes.
- **Rollback/containment note if blocked**:
  - Keep checkout disabled while preserving draft/preview capabilities.

## Day 6 — Control Center (users/roles/settings + RBAC UI gates)
- **Objective**: Enable tenant-safe administrative operations in Control Center.
- **Concrete deliverables**:
  - Users/roles/settings management screens.
  - RBAC gate components reflecting DENY > ALLOW and tenant ceiling.
  - Admin action audit-friendly UX copy.
- **Test gates**:
  - Role/permission UI matrix tests.
  - Unauthorized-action prevention checks.
- **Done means**:
  - Admin workflows function for authorized users and block unauthorized users by default.
- **Rollback/containment note if blocked**:
  - Release read-only admin dashboards while deferring mutation controls.

## Day 7 — E2E/UAT + internal alpha release + closure checkpoint
- **Objective**: Validate integrated tracks and close Sprint 7 with an internal alpha gate.
- **Concrete deliverables**:
  - Cross-app E2E/UAT execution report.
  - Internal alpha release notes and known-issues list.
  - Closure checkpoint artifact with pass/fail + deferred rationale.
- **Test gates**:
  - Full regression/smoke suite and contract-safety workflow green.
  - UAT sign-off checklist for P0 scope.
- **Done means**:
  - Alpha candidate approved with explicit residual-risk register and ownership.
- **Rollback/containment note if blocked**:
  - Hold alpha promotion; publish blocker report with remediation ETA and owners.
