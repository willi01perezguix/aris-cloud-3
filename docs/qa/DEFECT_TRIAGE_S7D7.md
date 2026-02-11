# Defect Triage — Sprint 7 Day 7

## Severity model
- **P0**: Data integrity, security/RBAC bypass, checkout rule violation, contract regression.
- **P1**: Major workflow failure with workaround unavailable.
- **P2**: Minor workflow degradation or UX/documentation issue.

## Fix-now vs defer criteria
- Fix now: any P0/P1 affecting closure blockers (auth, stock contract, POS preconditions, RBAC semantics).
- Defer: P2 issues with clear workaround and no API/business-rule impact.

## Current triage snapshot
| ID | Summary | Severity | Decision | Rationale |
|---|---|---|---|---|
| S7D7-DEF-001 | Mixed payment instruction copy lacks transfer voucher hint | P2 | Defer | UX-only, rule enforcement remains correct |

## Risks and mitigations
- Risk: hidden permission edge cases in tenant overrides.
  - Mitigation: keep deterministic deny-path tests in CI; require trace_id for failures.
- Risk: staging drift from deterministic fixtures.
  - Mitigation: manual `workflow_dispatch` staging smoke with `RUN_STAGING_E2E=1`.

## Hotfix decision criteria (post-alpha)
Trigger hotfix when any of the following occurs:
1. P0 issue reproduced in alpha and linked to current release candidate.
2. P1 affects >20% of tester flows or blocks checkout/user-management tasks.
3. Contract/rule regression detected in stock totals, action endpoints, idempotency, or payment prerequisites.

Hotfix readiness checklist:
- Repro with trace_id.
- Rollback plan validated.
- Focused regression suite green.
- Sign-off from module owner + release manager.
