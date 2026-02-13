# Degradation and Recovery Playbook v1 (Post-GA Day 3)

## Intent
Provide deterministic response steps for Day 3 load/observability degradations while preserving service behavior and API contracts.

## Trigger Conditions
- Probe gate result is NO-GO.
- Warning/critical alerts from Day 3 catalog fire.
- Latency, availability, or error-rate trend indicates unsafe envelope.

## Immediate Actions (First 10 Minutes)
1. Confirm scope: affected endpoints (`/health`, `/aris3/stock`, `/aris3/reports/overview`).
2. Freeze rollout/progression and annotate incident timeline.
3. Apply rollback-first decision if hard gates are breached.
4. Communicate status using the checklist in `POST_GA_DAY3_CAPACITY_CHARACTERIZATION.md`.

## Stabilization Sequence
1. Roll back to last known good release.
2. Validate health and primary read endpoints.
3. Confirm tenant-scope and RBAC enforcement unchanged.
4. Verify no idempotency/audit regression signals.
5. Execute L1 probe to re-establish GO baseline.

## Recovery Validation
- GO result in `artifacts/post-ga/day3/gate_result.txt`.
- Summary metrics under profile hard gates.
- No critical alerts active for 15+ minutes after rollback.

## Escalation
- Owner: Ops on-call.
- Secondary: Service owner.
- Tertiary: Incident commander.

## Roll-forward Prerequisites
- Root cause hypothesis documented.
- Mitigation reviewed and low-risk.
- L1 probe clean with reproducible artifacts.

## Explicit No-Contract-Drift Statement
This playbook governs operational response only and must not be used to justify API contract or business-rule changes during incident handling.

