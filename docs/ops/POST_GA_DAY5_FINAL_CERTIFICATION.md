# Post-GA Day 5 Final Certification

## Purpose
This package is the authoritative Day-5 release certification gate for ARIS v1. It verifies release stability without changing API contracts or business behavior.

## v1 Frozen Scope (explicit)
The following are frozen for v1 and cannot drift silently:
- API contract surface: endpoint paths, query/path params, request/response schemas, and response shape semantics.
- Stock/transfers/POS/cash/reports business rules and calculations.
- Tenant-scope, RBAC enforcement, audit logging guarantees, and idempotency behavior.
- `GET /aris3/stock` full-table contract.
- Edit-vs-action separation: `PATCH` remains data-edit only; all workflow state transitions remain under `/actions` routes.

## No Silent Drift Policy
- Any change that touches frozen scope requires explicit classification, evidence, and approval before merge.
- Unclassified or undocumented changes are treated as policy violations.
- Day-5 certification artifacts are immutable evidence for release sign-off.

## v1.1 Change Classification

### Patch
- Scope: non-contracting docs, operational scripts, CI/workflow hardening, defect fixes that do not alter behavior.
- Required evidence:
  - Targeted tests + full regression smoke relevant to touched area.
  - Change note describing zero contract drift.
  - Rollback note (revert commit/workflow disable path).

### Minor
- Scope: additive non-breaking features with unchanged v1 contracts/behavioral invariants by default path.
- Required evidence:
  - ADR with risk analysis and compatibility statement.
  - Focused functional tests + regression suite.
  - Rollback/feature-flag disabling plan with owner.

### Major
- Scope: any contract or behavior change, migration requiring coordinated rollout, or breaking UX/API assumptions.
- Required evidence:
  - Formal RFC/ADR set with stakeholder sign-off.
  - Migration + rollback runbook validated in rehearsal.
  - Versioning plan (new API version), deprecation path, and communication plan.

## GO/NO-GO Rubric
GO requires all:
1. Certification script status `GO`.
2. Required test sequence passes.
3. No frozen-scope drift detected.
4. Reliability and recovery evidence is complete (or explicitly marked incomplete with no hard fails when strict gate disabled).

NO-GO triggers:
- Hard-fail evidence in strict mode.
- Missing mandatory evidence for declared change class.
- Detected contract drift or business invariant drift.
- Unowned SEV response path or missing rollback notes.

## Day-5 Artifact Set
- `artifacts/post-ga/day5/reliability_summary.json`
- `artifacts/post-ga/day5/recovery_readiness.json`
- `artifacts/post-ga/day5/environment_fingerprint.json`
- `artifacts/post-ga/day5/certification_gate_result.txt`
- `artifacts/post-ga/day5/certification_manifest.json`
