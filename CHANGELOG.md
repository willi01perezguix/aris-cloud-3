# Changelog

## 0.1.0-rc.9 - Sprint 7 Day 5 (ARIS-CORE-3 POS Sales + POS Cash integration)

### Added
- ARIS-CORE-3 POS integration service layer: `pos_sales_service.py` and `pos_cash_service.py` using existing SDK routes/contracts only.
- POS view-model wiring under `clients/python/apps/core_app/ui/pos/` for sales draft/edit/checkout/cancel, payment summary, cash session actions, and cash movement visibility.
- POS test suite under `clients/python/tests/core_app/pos/` covering draft/edit/checkout/cancel, payment validation rules, cash open-session precondition, cash action state gating, permission gating, and mapped error UX behavior.
- Dedicated POS CI workflow: `.github/workflows/clients-python-core-app-pos.yml` for lint, type checks, and POS tests on pull requests.

### Changed
- Core app README now documents Sprint 7 Day 5 POS lifecycle flows, payment rules, cash-session preconditions, permission requirements, and known limitations.

### Notes
- POS critical mutations wire `transaction_id` and `idempotency_key` metadata.
- No contract-breaking API changes were introduced, and no new backend endpoints were added.

## 0.1.0-rc.8 - Sprint 7 Day 4 (ARIS-CORE-3 Stock module integration)

### Added
- ARIS-CORE-3 stock integration service and UI view-models for official full-table stock query, totals rendering, EPC import, SKU import, and SKU→EPC migration under `clients/python/apps/core_app/`.
- Stock module tests under `clients/python/tests/core_app/stock/` covering list rendering, filter pass-through, EPC/SKU validation enforcement, migration payload + idempotency wiring, permission gating, and error mapping.

### Changed
- Core-app CI workflow now lints/types/tests stock module files in addition to Day 3 shell scope.
- Core app README now documents stock list/filter behavior, import/migration flows, permission requirements, and current limitations.

### Notes
- Stock mutations include transaction and idempotency metadata wiring through SDK critical operations.
- No contract-breaking API changes were introduced, and no new backend endpoints were added.

## 0.1.0-rc.7 - Sprint 7 Day 3 (ARIS-CORE-3 app shell foundation)

### Added
- ARIS-CORE-3 Day 3 app shell foundation under `clients/python/apps/core_app/` with bootstrap, state, navigation skeleton, auth/profile/permissions services, and UI placeholder widgets/views.
- Authentication bootstrap flow covering session check, login routing, `/aris3/me` profile hydration, must-change-password route, permission load, and logout/session clear behaviors.
- Effective-permissions default-deny gate (deny-over-allow) wired to module-level navigation rendering for Stock, Transfers, POS Sales, POS Cash, Inventory Counts, Reports, Exports, and Admin/Settings.
- Core app shell auth/permission tests in `clients/python/tests/core_app/test_bootstrap.py`.
- CI workflow `.github/workflows/clients-python-core-app.yml` for lint, type checks, and core app tests on PRs.

### Notes
- Scope remains app-shell/auth/permissions foundation only; module panels are placeholders for upcoming sprint days.
- No contract-breaking API changes were introduced, and no new backend endpoints were added.

## 0.1.0-rc.6 - Sprint 7 Day 2 (Python SDK hardening)

### Added
- Python SDK transport hardening with explicit retries/backoff/connection-pool controls and deterministic transport error mapping.
- Centralized idempotency helper utilities for transaction and idempotency key propagation in critical mutations.
- New SDK CI workflow for lint, type-check, and tests: `.github/workflows/clients-python-sdk.yml`.
- Sprint 7 app-team quickstart example: `clients/python/examples/sdk_quickstart.py`.

### Changed
- Auth/session handling hardened (must-change-password structured exception, safe auth store read/clear behavior, explicit logout utility).
- Error mapping normalized to stable SDK exception families with preserved server payload debug fields.
- Base client metadata propagation for trace/tenant/app/device headers without bypassing RBAC constraints.
- Stock client idempotency helper exposure for safer critical mutation calls while preserving stock full-table contract handling.
- Python SDK packaging/tooling updated with dev quality gates (ruff, mypy, pytest).

### Notes
- Python SDK hardening completed with resilience/error/idempotency improvements, tests and CI reinforced.
- No contract-breaking API changes were introduced.

## 0.1.0-rc.5 - Sprint 7 Day 1 (Kickoff, backlog, contract safety baseline)

### Added
- Sprint 7 kickoff artifact: `docs/planning/SPRINT7_DAY1_KICKOFF.md`.
- Prioritized backlog master with P0/P1/P2/deferred breakdown: `docs/planning/SPRINT7_BACKLOG_MASTER.md`.
- Day-by-day execution plan for Days 2–7: `docs/planning/SPRINT7_EXECUTION_PLAN_D2_D7.md`.
- Sprint board governance template with DoR/DoD and blocker escalation policy: `docs/planning/SPRINT7_BOARD_TEMPLATE.md`.
- Contract safety guardrail script with strict/json modes: `scripts/contract_safety_check.py`.
- Contract safety CI workflow for PRs to `main`: `.github/workflows/contract-safety.yml`.

### Notes
- Sprint 7 Day 1 kickoff completed with planning baseline and execution structure.
- Contract safety checks introduced and wired for CI evidence artifacts.
- No contract-breaking API changes were introduced.

## 0.1.0-rc.4 - Sprint 6 Day 8 (Post-go-live stabilization and closure)

### Added
- Stabilization/defect triage log: `docs/releases/STABILIZATION_LOG_S6D8.md`.
- Final release closure package: `docs/releases/FINAL_RELEASE_CLOSURE_S6D8.md`.
- SLI/SLO baseline lock artifact: `docs/ops/SLI_SLO_BASELINE_S6D8.md`.
- Non-destructive integrity CLI with strict/json modes: `scripts/post_go_live_integrity_check.py`.
- Post-go-live smoke regression suite: `tests/smoke/test_post_go_live_stability.py`.
- Hotfix protocol runbook and readiness helper: `runbooks/13_HOTFIX_PROTOCOL_ARIS3_v1.md`, `scripts/hotfix_readiness_check.py`.
- Stability CI workflow for PRs and nightly schedule: `.github/workflows/post-go-live-stability.yml`.

### Changed
- Go-live, hypercare, and recovery runbooks synced with Day 8 validated command blocks.

### Notes
- No contract-breaking API changes were introduced.

## 0.1.0-rc.2 - Sprint 6 Day 6 (Post-merge stabilization)

### Added
- Consolidated release readiness gate script `scripts/release_readiness_gate.py` with blocker-aware summary and checks for smoke, migration safety, security sanity, readiness, and local performance p95 budget.
- Post-merge critical smoke suite in `tests/smoke/test_post_merge_readiness.py` covering auth, stock contract/totals, transfer lifecycle, POS checkout preconditions, reports/exports availability, and idempotency replay checks.
- Dedicated CI workflow `.github/workflows/release-readiness.yml` for PRs to `main` with sqlite and postgres gate runs.

### Changed
- Recovery runbook updated with executable verification flow and rollback verification steps aligned to release readiness gate commands.

### Notes
- No contract-breaking API changes were introduced.

## 0.1.0-rc.3 - Sprint 6 Day 7 (RC sign-off, go-live, hypercare)

### Added
- RC final sign-off package: `docs/releases/RC_FINAL_SIGNOFF_S6D7.md`.
- Go/No-Go decision checklist: `docs/releases/GO_NO_GO_CHECKLIST_S6D7.md`.
- Controlled go-live playbook with staged deployment, rollback triggers, rollback execution, and communication templates: `runbooks/11_GO_LIVE_PLAYBOOK_ARIS3_v1.md`.
- Hypercare runbook with SLI/SLO guardrails, escalation paths, triage tree, and stabilization exit criteria: `runbooks/12_HYPERCARE_RUNBOOK_ARIS3_v1.md`.
- Day 7 post-deploy smoke validation suite: `tests/smoke/test_go_live_validation.py`.
- Optional preflight automation command: `scripts/go_live_checklist.py`.
- Final release notes artifact: `docs/releases/RELEASE_NOTES_S6D7.md`.

### Changed
- Release-readiness CI workflow now runs Day 7 go-live smoke validation in both sqlite and postgres jobs.

### Notes
- No contract-breaking API changes were introduced.
