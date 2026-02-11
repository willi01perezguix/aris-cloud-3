# Alpha Feedback Consolidated — Sprint 8 Day 1

Source inputs consolidated from Sprint 7 Day 7 artifacts:
- `docs/qa/UAT_RESULTS_SPRINT7_DAY7.md`
- `docs/qa/SPRINT7_DAY7_E2E_MATRIX.md`
- `docs/qa/OBSERVABILITY_EVIDENCE_S7D7.md`
- `docs/qa/DEFECT_TRIAGE_S7D7.md`
- `docs/releases/INTERNAL_ALPHA_NOTES_S7D7.md`

## Consolidated issue list
| ID | Summary | Severity | Module tag | Repro quality (1-5) | Confidence | Decision | Rationale |
|---|---|---|---|---:|---:|---|---|
| S8-AF-001 | Login/session error messaging lacks consistent actionable hint for expired auth | P1 | core_app | 4 | 4 | fix-now | High-impact operator interruption in first-mile flow; deterministic repro available |
| S8-AF-002 | Control Center deny-state messaging not explicit enough for delegated admins | P1 | control_center | 3 | 4 | fix-now | Prevents safe self-service remediation and drives support load |
| S8-AF-003 | Stock list loading states occasionally appear blank before error banner renders | P2 | core_app | 3 | 3 | schedule | UX degradation but no rule/contract risk; queue for D2 polish |
| S8-AF-004 | Transfer voucher hint copy is inconsistent with checkout validator wording | P2 | sdk | 5 | 4 | schedule | Validation correct; wording consistency improves beta usability |
| S8-AF-005 | Alpha package install docs miss explicit Windows SmartScreen recovery step | P2 | packaging | 5 | 5 | fix-now | Repeated onboarding friction for pilot tenants |
| S8-AF-006 | Contract-rule reminder missing from day-start QA checklist | P2 | ci | 4 | 4 | fix-now | Procedural risk; low-cost mitigation in CI/gate docs |
| S8-AF-007 | One UAT report lacked trace_id on captured failure screenshot metadata | P3 | qa | 2 | 2 | defer | Process issue; mitigate via telemetry baseline and template update later |
| S8-AF-008 | RBAC matrix export formatting wraps long policy names in reports | P3 | control_center | 4 | 3 | defer | Cosmetic, non-blocking for beta-readiness baseline |

## Severity totals
- **P0:** 0
- **P1:** 2
- **P2:** 4
- **P3:** 2

## Module distribution
- `core_app`: 2
- `control_center`: 2
- `sdk`: 1
- `packaging`: 1
- `ci`: 1
- `qa`: 1

## Decision breakdown
- **fix-now:** 4
- **schedule (D2–D7):** 2
- **defer:** 2
