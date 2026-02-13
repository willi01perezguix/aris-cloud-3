# GA Deployment Handoff

## Purpose
Operational handoff checklist for GA deployment execution and support readiness.

## Deployment Prerequisites
- Main branch merged with GA finalization commit and green CI.
- Validation matrix completed (see `docs/releases/GA_TEST_EVIDENCE.md`).
- Environment configuration validated (database connectivity, secrets, tenant config).
- Backups/snapshots taken for production data stores prior to deployment.

## Rollback Triggers
Trigger rollback if any of the following occurs:
- Contract deviation detected in smoke validation.
- Critical workflow failure in POS checkout / reports exports.
- RBAC, tenant scoping, or audit trail regression.
- Error budget breach in early post-deploy validation window.

## Rollback Actions
1. Halt rollout and notify incident channel.
2. Revert to last known-good release tag.
3. Re-run smoke checks and reports export validation.
4. Capture incident timeline and attach logs/artifacts.

## Owner Checklist
### Dev Owner
- [ ] Confirm release manifest and version metadata.
- [ ] Confirm GA gate scripts/workflow are green.
- [ ] Confirm no API/business-rule drift.

### QA Owner
- [ ] Confirm all six validation commands pass.
- [ ] Confirm non-blocking warnings are documented.
- [ ] Sign off on GO recommendation.

### Ops Owner
- [ ] Confirm prerequisites completed.
- [ ] Confirm rollback plan is staged and reachable.
- [ ] Execute and monitor deployment handoff window.
