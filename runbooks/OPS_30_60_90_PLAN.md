# ARIS v1 Operations 30/60/90 Plan

## 0-30 Days (stabilize and observe)
- Weekly health checks: API error rate, latency p95, queue depth, export/report success ratio.
- Weekly cost review: infra spend vs Day-4 baseline; investigate >10% variance.
- Weekly reliability review: incident timeline and mitigation tracking.
- First DR drill (tabletop + restore verification) before day 30 close.
- Confirm Day-5 certification artifacts are generated on each manual gate run.

## 31-60 Days (optimize and harden)
- Continue weekly health and cost cadence.
- Monthly full recovery drill with RTO/RPO capture.
- Validate on-call handoff quality via at least one SEV simulation.
- Review and tighten alert thresholds based on observed noise/coverage.
- Start v1.1 intake triage under frozen baseline policy.

## 61-90 Days (institutionalize)
- Monthly executive readiness report (stability, cost, risk, pending changes).
- Monthly compliance review for RBAC/tenant/audit/idempotency controls.
- Quarterly-style DR rehearsal dry run (expanded scenario matrix).
- Finalize steady-state release train and ownership SLA scorecards.

## Cadence (ongoing)
- Weekly:
  - reliability health check
  - incident review and action tracking
  - cost variance triage
- Monthly:
  - DR drill
  - access review and ownership validation
  - release train retrospective

## v1.1+ Release Train Proposal
- Cadence: 2-week train with explicit intake cutoff.
- Train entry criteria: change class assigned, evidence complete, rollback notes present.
- Train exit criteria: certification gate `GO`, regression suite pass, artifacts published.

## Ownership Placeholders
- Ops Accountable: `<ops-accountable-role>`
- Service Owner: `<service-owner-role>`
- QA Owner: `<qa-owner-role>`
- Platform Backup: `<platform-backup-role>`
- Security Backup: `<security-backup-role>`
