# Cost Budgets and Thresholds v1

## Scope
Operational CI/runtime and artifact-storage governance only.

## Thresholds
- CI runtime envelope (required Day gates):
  - Pass: < 900s
  - Warn: >= 900s and < 1200s
  - Fail: >= 1200s
- Artifact footprint (post-ga artifacts total):
  - Pass: < 250MB
  - Warn: >= 250MB and < 500MB
  - Fail: >= 500MB

## Breach actions
- Warn: annotate run summary and create owner follow-up within one business day.
- Fail: set NO-GO, execute rollback-first, and escalate to on-call.

## Contract safety statement
Budgets never alter endpoint behavior; they only report and gate operational readiness.
