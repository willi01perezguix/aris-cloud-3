# Internal Alpha Notes — Sprint 7 Day 7

## Release headline
Sprint 7 closes with validated cross-module flows, UAT evidence, CI-hardening, and alpha-ready packaging guidance.

## What internal testers should verify
- End-to-end auth/bootstrap/logout.
- Effective-permissions gating behavior (default deny + DENY precedence).
- Stock full-table responses and totals invariants.
- POS draft/edit/checkout/cancel and payment rule enforcement.
- Control Center users actions, RBAC ceiling behavior, and settings updates.

## Risk posture
- Contract stability preserved (no endpoint contract changes).
- Residual risk is limited to non-blocking UX copy refinement for mixed payment guidance.

## Support expectations
- Include trace_id in every defect.
- Use UAT script and defect template in `docs/qa/UAT_SCRIPT_SPRINT7_DAY7.md`.
- Triage policy follows `docs/qa/DEFECT_TRIAGE_S7D7.md`.
