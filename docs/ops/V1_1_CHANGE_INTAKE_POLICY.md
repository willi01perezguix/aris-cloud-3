# v1.1 Change Intake Policy

## Objective
Provide strict intake controls for v1.1+ while preserving the frozen v1 baseline.

## Intake Rules
1. Every request is tagged `patch`, `minor`, or `major` before implementation.
2. Every request includes owner, risk class, rollback notes, and test plan.
3. Frozen v1 scope can only be touched with explicit exception approval.
4. No silent drift: undocumented behavior/contract changes are rejected.

## Required Evidence by Class

### Patch
- Linked issue + concise change note.
- Targeted tests for touched surfaces.
- Revert/rollback instructions.

### Minor
- ADR with compatibility analysis.
- Functional tests + regression evidence.
- Rollout and rollback plan (including owner + backout trigger).

### Major
- RFC/ADR bundle with architecture + product sign-off.
- Migration plan, data safety checks, and rollback rehearsal.
- Versioning/deprecation strategy and release communication plan.

## Review and Approval Matrix
- Patch: service owner + QA lead.
- Minor: service owner + QA lead + platform/reliability approver.
- Major: architecture council + product + security + operations.

## Gate Result Semantics
- `GO`: evidence complete, risk accepted, rollback path validated.
- `NO-GO`: missing evidence, unresolved high-risk item, or frozen-scope violation.
- `INCOMPLETE EVIDENCE`: intake item remains queued until missing artifacts are supplied.
