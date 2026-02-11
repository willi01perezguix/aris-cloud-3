# Sprint 8 Day 1 Kickoff — Beta-Readiness Hardening Baseline

## Sprint 8 objective
Sprint 8 focuses on **beta-readiness hardening** for ARIS-CORE-3 and Control Center after Sprint 7 Day 7 alpha closure. Day 1 establishes the operational baseline: feedback triage, prioritized hardening backlog, execution sequencing, and rollout-safety scaffolding.

## Scope boundaries
### In scope
- Alpha/UAT feedback consolidation and triage into actionable sprint decisions.
- Prioritized Day 2–Day 7 hardening backlog with ownership placeholders.
- Execution plan with day-level objectives, tests, and done criteria.
- Lightweight non-PII telemetry scaffolding and safe-by-default feature flag scaffolding.
- Regression and contract-safety gate reinforcement with CI visibility.

### Out of scope
- Contract-breaking API changes.
- New backend endpoint invention.
- Broad product feature expansion outside hardening targets.
- RBAC semantics redesign.

## Module map
| Module | Focus in Sprint 8 | Primary outcomes |
|---|---|---|
| Python SDK / shared client utilities | rollout safety + diagnostics substrate | telemetry and feature flag scaffolds with tests |
| ARIS-CORE-3 app | operator hardening and UX safety | robust error states, permission-safe rollouts |
| Control Center app | admin safety rails + RBAC UX hardening | deny-first controls and clearer guardrails |
| CI/QA | regression confidence | beta readiness gate + artifact-rich CI checks |

## Owners and handoff model
| Role | Owner | Responsibilities | Daily handoff artifact |
|---|---|---|---|
| Sprint lead | _TBD_ | Scope control, blocker escalation, risk arbitration | Day status with blocker disposition |
| QA/triage owner | _TBD_ | Feedback intake quality and severity governance | Updated triage board and counts |
| Core app owner | _TBD_ | Core hardening execution and UX regressions | Core app delta + regression evidence |
| Control Center owner | _TBD_ | RBAC/admin hardening delivery | Permission safety evidence |
| Shared platform owner | _TBD_ | telemetry, flags, gate/CI baseline | Tooling summary and CI artifact links |

## Top risks and mitigations
| Risk | Mitigation | Trigger signal |
|---|---|---|
| Contract drift during hardening | Preserve strict contract-safety checks in baseline gate | contract check fails in PR |
| Hidden alpha repro gaps | Add repro-quality score and confidence in triage board | low-score items linger without owner |
| Rollout noise without diagnostics | non-PII telemetry scaffold with trace correlation fields | unresolved error reports without trace context |
| Feature flag misuse | flags default OFF and explicit no-permission-bypass rule | flagged UI surfaces action without permission |
| Regression debt accumulation | deterministic smoke + scoped unit checks in CI | merge requests with missing gate evidence |

## Contract safety first
**Contract safety first is non-negotiable for Sprint 8.** All hardening work must preserve frozen behavior:
- `GET /aris3/stock` remains official full-table output (`meta/rows/totals`, full columns).
- PATCH remains data-edit only, state transitions only via `/actions`.
- Inventory and checkout/payment/idempotency/RBAC frozen rules remain intact.
