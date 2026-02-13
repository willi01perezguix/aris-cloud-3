# Hotfix Protocol v1

## Objective
Deliver safe, fast recovery under incident pressure with strict no-contract-drift guarantees.

## Guardrails
1. No API contract drift (paths, params, schemas).
2. No business-rule drift (stock/transfers/POS/reports).
3. Preserve idempotency, tenant scope, RBAC, audit guarantees.
4. Prefer reversible changes and evidence-backed execution.

## Decision Tree (Rollback-first vs Forward-fix)
1. **Is there customer-impacting degradation?**
   - No: continue monitoring and defer to normal release train.
   - Yes: continue.
2. **Is rollback path available and low risk?**
   - Yes: execute rollback-first.
   - No: continue.
3. **Can forward-fix be applied without contract/behavior drift?**
   - Yes: approve scoped forward-fix.
   - No: NO-GO for hotfix; apply containment + escalate.
4. **Validation gates pass?**
   - No: stop and revert/contain.
   - Yes: deploy and monitor.

## Execution Checklist
- [ ] Incident severity assigned (SEV0-3).
- [ ] Blast radius documented (tenant/system/user scope).
- [ ] Contract drift check completed and signed by Dev+QA.
- [ ] Rollback command path pre-validated.
- [ ] Required smoke tests passed.
- [ ] Audit trail updated (ticket/PR/changelog).

## Ownership and SLA
| Phase | Dev | QA | Ops |
|---|---|---|---|
| Triage | Root cause hypothesis in 15 min (SEV0/1) | Repro confirmation | Impact + telemetry confirmation |
| Mitigation | Rollback/fix implementation | Verification evidence | Deployment execution + monitoring |
| Closure | Patch notes + follow-up owners | Regression risk assessment | Incident comms finalization |

## GO / NO-GO for Hotfix Release
### GO
- Mitigation path is reversible.
- No contract drift.
- Smoke checks pass.
- Incident communication sent.

### NO-GO
- Contract drift required to fix.
- Unknown tenant impact.
- Rollback unverified.
- Validation evidence incomplete.
