# Sprint 7 Day 1 Kickoff

## Sprint 7 objective statement
Sprint 7 targets **product hardening and app-track execution** across the Python SDK, ARIS-CORE-3, and Control Center while preserving ARIS contract integrity. Day 1 establishes execution discipline, backlog clarity, and guardrails so Days 2–7 can deliver safely and predictably.

## Scope boundaries
### In scope
- Planning and execution baselines for Sprint 7.
- Backlog creation with prioritization, ownership placeholders, acceptance criteria, and risk.
- Contract-safety reinforcement through lightweight automated checks and CI gate integration.
- Day-by-day execution sequencing for SDK, ARIS-CORE-3 app, Control Center app, and E2E/UAT.

### Out of scope
- Contract-breaking API behavior changes.
- Broad architecture rewrites or schema redesign.
- Feature expansion without acceptance criteria and risk ownership.
- Non-essential refactors that reduce delivery focus for Days 2–7.

## Dependency map
| Track | Primary dependencies | Downstream consumers | Critical integration points |
|---|---|---|---|
| API Core | DB models, repositories, router contracts, RBAC | SDK, ARIS-CORE-3, Control Center | `/aris3/stock`, `/actions`, idempotency/concurrency invariants |
| Python SDK | Stable API schemas, auth flow, paging/totals format | ARIS-CORE-3 app, automation clients | stock full-table read, critical mutation envelopes |
| ARIS-CORE-3 app | SDK capability parity, auth/me, effective permissions | Store and ops workflows | stock/import/migrate/POS integration with permission-aware UX |
| Control Center app | RBAC/tenant/user endpoints, SDK/admin APIs | Tenant admins and platform operators | users/roles/settings workflows and DENY-first policy UI gating |

## Roles, owners, and handoffs
| Role | Owner | Responsibilities | Handoff expectations |
|---|---|---|---|
| Sprint lead | _TBD_ | Prioritization, risk arbitration, scope control | Daily checkpoint with all module owners |
| API hardening owner | _TBD_ | Contract checks, endpoint safety, mutation guardrails | Publish daily contract-safety status |
| SDK owner | _TBD_ | Python SDK hardening and release packaging | Versioned SDK handoff notes to app teams |
| ARIS-CORE-3 owner | _TBD_ | App shell + integrations + UX gates | Demo-ready build plus acceptance evidence |
| Control Center owner | _TBD_ | RBAC-focused admin workflows and UI gates | Permission matrix validation report |
| QA/UAT owner | _TBD_ | Test gates, E2E/UAT coordination, defect triage | Day 7 alpha sign-off packet |

## Risk register (top 10)
| # | Risk | Mitigation | Trigger signal |
|---|---|---|---|
| 1 | Contract drift in stock response shape | Run contract safety checks in CI and local strict mode | Missing `meta/rows/totals` in static guardrail check |
| 2 | State-transition logic leaks into non-`/actions` routes | Detect suspicious transition endpoints and enforce review | Guardrail emits suspicious routes outside `/actions` |
| 3 | TOTAL invariant regressions (`TOTAL != RFID + PENDING`) | Static hook + targeted smoke assertions before merge | Check report indicates missing invariant expression/hook |
| 4 | Idempotency drift in critical mutations | Preserve transaction + idempotency envelope patterns | Code review flags missing `transaction_id`/`idempotency_key` |
| 5 | RBAC regression in app tracks | DENY-first UI and API permission matrix checks | Unauthorized behavior observed in UAT smoke |
| 6 | SDK/API version mismatch | Pin API compatibility target and daily sync | SDK integration breakage on Day 3/4 demos |
| 7 | Cross-team dependency blocking | Daily handoff artifact and explicit unblock owner | Ticket aging >1 day in Blocked without escalation |
| 8 | Test debt accumulation | Daily gate checklist and defect ownership | Increasing flaky/failing smoke counts |
| 9 | Scope creep mid-sprint | Strict P0/P1 gate and deferred rationale tracking | Unplanned items entering In Progress without triage |
| 10 | CI blind spots for contract-critical modules | Add contract safety workflow + artifact upload | PR merged without contract check evidence |

## Contract safety first statement
Sprint 7 execution is governed by **contract safety first**: all delivery work must preserve frozen contract rules, especially stock full-table output, `/actions`-only state transitions, inventory totals invariants, idempotency/concurrency controls, and DENY-first RBAC boundaries.
