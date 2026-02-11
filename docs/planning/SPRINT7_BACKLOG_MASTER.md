# Sprint 7 Backlog Master (Prioritized)

## 1) Must-have (P0)

| ID | Title | Module | User impact | Technical notes | Acceptance criteria | Owner | Risk | Effort |
|---|---|---|---|---|---|---|---|---|
| S7-P0-01 | Python SDK contract lock and typed stock client hardening | sdk | Prevents integration churn for app teams consuming stock/import/POS endpoints | Align SDK response models to frozen API contracts, preserve idempotency fields in mutation methods | SDK methods for critical flows expose typed request/response and pass contract smoke checks | _TBD_ | High | M |
| S7-P0-02 | ARIS-CORE-3 app shell with auth/me + effective permissions | core app | Enables safe app bootstrap with correct user context and access visibility | Implement auth bootstrap path, effective-permission fetch, and deny-first rendering defaults | User can sign in, load profile, and see permission-driven shell routes without unauthorized leaks | _TBD_ | High | M |
| S7-P0-03 | Stock/Imports/Migrate app integration using contract-safe flows | core app | Allows core inventory execution without manual API operations | Bind UI flows to `/aris3/stock`, `/import-epc`, `/import-sku`, `/migrate-sku-to-epc`, `/actions` | Full-table stock view and import/migrate actions complete with validation and evidence logs | _TBD_ | High | L |
| S7-P0-04 | POS Sales + POS Cash critical path integration | core app | Unlocks store transaction lifecycle with accurate stock deductions and cash capture | Enforce EPC/RFID and SKU/PENDING sell rules; session-aware cash controls | Checkout, return, and cash session flows run in smoke tests with invariant-safe outcomes | _TBD_ | High | L |
| S7-P0-05 | Control Center users/roles/settings with RBAC UI gates | control center | Admin users can safely manage users and permissions | Implement gate components honoring DENY > ALLOW and tenant ceiling | Admin UI blocks unauthorized actions and supports role/user management happy paths | _TBD_ | High | M |
| S7-P0-06 | Contract safety checks + CI enforcement | api hardening / ci | Reduces risk of accidental contract breaks on PRs | Add script + workflow for stock contract, route sanity, invariants, and `/actions` boundaries | PR to `main` fails on contract-safety violations and uploads diagnostic artifact | _TBD_ | Medium | S |
| S7-P0-07 | Sprint execution evidence discipline | docs / ci | Improves delivery predictability and review quality | Standardize daily evidence artifact requirements and merge checklist | Each sprint-day PR contains evidence for acceptance checks and risk disposition | _TBD_ | Medium | S |

## 2) Should-have (P1)

| ID | Title | Module | User impact | Technical notes | Acceptance criteria | Owner | Risk | Effort |
|---|---|---|---|---|---|---|---|---|
| S7-P1-01 | SDK retry/backoff + richer error mapping | sdk | Better resilience and debuggability for integrators | Add configurable retry strategy for transient failures and structured error classes | Integration tests validate retry behavior and surfaced error metadata | _TBD_ | Medium | M |
| S7-P1-02 | ARIS-CORE-3 observability hooks (trace IDs, UX diagnostics) | core app | Faster triage during alpha/UAT | Thread request/trace context through app state and logs | Reproducible logs correlate app actions to backend traces | _TBD_ | Medium | M |
| S7-P1-03 | Control Center bulk role assignment and audit hints | control center | Reduces admin overhead at scale | Add safe bulk assignment workflow with confirmation and audit context | Bulk changes work with rollback-safe UX and deny-first prechecks | _TBD_ | Medium | M |
| S7-P1-04 | API hardening smoke expansions for idempotent mutations | api hardening | Improves confidence in mutation safety | Extend smoke checks for transaction_id/idempotency_key replay semantics | Replay-safe behavior validated in CI smoke suite | _TBD_ | Medium | M |
| S7-P1-05 | Cross-track integration fixtures for local dev | ci / docs | Speeds up onboarding and reproducible testing | Curate fixtures and commands for SDK/core/control-center integration | Teams can run documented local integration pack end-to-end | _TBD_ | Low | S |

## 3) Nice-to-have (P2)

| ID | Title | Module | User impact | Technical notes | Acceptance criteria | Owner | Risk | Effort |
|---|---|---|---|---|---|---|---|---|
| S7-P2-01 | SDK async client parity | sdk | Improves performance options for advanced consumers | Add async variants mirroring core sync APIs | Async client passes parity tests on key endpoints | _TBD_ | Low | L |
| S7-P2-02 | ARIS-CORE-3 keyboard-first operator shortcuts | core app | Better power-user efficiency | Introduce non-invasive shortcut layer with permission-aware actions | Shortcuts documented and disabled for unauthorized operations | _TBD_ | Low | M |
| S7-P2-03 | Control Center saved views/filters | control center | Improves admin workflow throughput | Persist UI filter state with tenant-safe defaults | Users can save/apply views without violating access rules | _TBD_ | Low | M |
| S7-P2-04 | Dashboard quality-of-life metrics page | docs / control center | Better internal visibility | Provide lightweight internal metrics page and glossary | Metrics view available and linked from operations docs | _TBD_ | Low | M |

## 4) Deferred (explicit rationale)

| ID | Title | Module | User impact | Technical notes | Acceptance criteria | Owner | Risk | Effort | Deferred rationale |
|---|---|---|---|---|---|---|---|---|---|
| S7-DEF-01 | v2 fallback sale behavior (SKU fallback to RFID) | api hardening | Potential future flexibility for mixed-stock checkout | Conflicts with frozen v1 sale semantics; requires contract revision process | Deferred until formal v2 contract RFC approved | _TBD_ | High | L | Explicitly out-of-scope for Sprint 7 due to frozen contract rule |
| S7-DEF-02 | RBAC policy model redesign | api hardening / control center | Could simplify long-term policy management | High migration and regression risk mid-hardening sprint | Deferred until post-alpha architecture window | _TBD_ | High | L | Avoid destabilizing DENY-first semantics during hardening |
| S7-DEF-03 | Multi-tenant global reporting revamp | core app / api | Broader analytics value but limited Sprint 7 criticality | Requires additional schema/index work and governance alignment | Deferred until dedicated reporting sprint | _TBD_ | Medium | L | Preserve focus on hardening and app-track execution |
| S7-DEF-04 | Cross-region active-active experimentation | ci / ops | Long-term availability gain | Infrastructure-heavy and outside Day 2–7 objectives | Deferred to platform roadmap | _TBD_ | Medium | L | Not required for Sprint 7 alpha scope |
