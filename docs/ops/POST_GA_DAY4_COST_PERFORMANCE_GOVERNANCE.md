# Post-GA Day 4 Cost/Performance Governance

## Objective
Establish additive operational governance for cost/performance control after GA without changing API contracts, endpoint shapes, or business behavior.

## Guardrails
- No API contract drift (paths/query/schema/response shape unchanged).
- Rollback-first principle for governance regressions: disable Day-4 workflow/script usage before any functional code touch.
- No change to stock/transfers/POS/reports business rules.

## CI/Runtime budget targets
- Unit/scaffold checks target: <= 180s total.
- Smoke checks target: <= 300s total.
- Full test suite envelope target: warn at 900s, critical at 1200s.

## Artifact storage assumptions
- Post-GA operational artifacts are retained under `artifacts/post-ga/**`.
- Storage budget: warn at 250MB total rolling footprint, critical at 500MB.
- Day-4 cleanup tooling is dry-run first; destructive cleanup is opt-in.

## Performance budget references
- Day-2 runtime and duration logs are treated as baseline source of truth.
- Day-3 load probe p95/p99 and error-rate are continuity references for Day-4 budget checks.
- Day-4 analyzer reports pass/warn/fail only; no runtime behavior modifications.

## Budget breach response playbook
### Warn
1. Record breach in Day-4 summary artifacts.
2. Open ops follow-up issue and assign owner.
3. Keep release posture unchanged; monitor next run.

### Critical
1. Mark governance result as NO-GO in artifacts.
2. Trigger rollback-first action: stop promotion and revert operational workflow usage to last known good baseline.
3. Escalate to on-call owner and incident channel.

## Rollback-first principle
If governance scripts/workflow produce unstable results, revert only Day-4 governance additions and rerun prior Day-3/Day-2 baselines. Functional code remains untouched.
