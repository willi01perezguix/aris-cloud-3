# Defect Triage Board — Sprint 8 Day 1

## Severity policy
- **P0:** data integrity/security/RBAC bypass/contract break.
- **P1:** major workflow failure without acceptable workaround.
- **P2:** moderate quality issue with workaround.
- **P3:** minor quality/cosmetic/documentation issue.

## Triage board
| ID | Severity | Module | Repro quality (1-5) | Confidence (1-5) | Decision | Owner | Target day | Notes |
|---|---|---|---:|---:|---|---|---|---|
| S8-AF-001 | P1 | core_app | 4 | 4 | fix-now | _TBD_ | D2 | Normalize expired session error states and retry CTA |
| S8-AF-002 | P1 | control_center | 3 | 4 | fix-now | _TBD_ | D3 | Deny-state UX copy and admin safety rail guidance |
| S8-AF-003 | P2 | core_app | 3 | 3 | schedule | _TBD_ | D2 | Improve loading skeleton/error transition behavior |
| S8-AF-004 | P2 | sdk | 5 | 4 | schedule | _TBD_ | D4 | Unify transfer/check-out validator hint strings |
| S8-AF-005 | P2 | packaging | 5 | 5 | fix-now | _TBD_ | D5 | Add SmartScreen recovery step and troubleshooting |
| S8-AF-006 | P2 | ci | 4 | 4 | fix-now | _TBD_ | D2 | Add contract reminder and gate summary capture |
| S8-AF-007 | P3 | qa | 2 | 2 | defer | _TBD_ | backlog | Improve trace_id capture template after baseline week |
| S8-AF-008 | P3 | control_center | 4 | 3 | defer | _TBD_ | backlog | Report formatting tidy-up only |

## Fix/defer rationale standards
- **fix-now:** P0/P1 or high-confidence P2 issue that blocks beta operator/admin confidence.
- **schedule:** Valid issue with moderate impact and clear fit into D2–D7 execution windows.
- **defer:** Low impact or low confidence; maintain explicit rationale and reevaluate at mid-sprint.

## Escalation rule
Any new **P0** discovered during Sprint 8 is immediate blocker and supersedes scheduled D2–D7 work until containment is validated.
