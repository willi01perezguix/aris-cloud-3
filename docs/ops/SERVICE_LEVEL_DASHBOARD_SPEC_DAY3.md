# Service-Level Dashboard Spec - Day 3

## Objective
Define a minimum, actionable dashboard for Day 3 controlled capacity characterization and incident response.

## Dashboard Panels
1. **Availability**
   - Global availability (5m, 1h)
   - Per-endpoint availability for `/health`, `/aris3/stock`, `/aris3/reports/overview`
2. **Latency**
   - p50/p95/p99 overall
   - p95 per endpoint
3. **Error Rate**
   - overall error rate trend
   - non-2xx breakdown by endpoint
4. **Saturation Proxy**
   - timeout count trend
   - request queue or in-flight proxy trend (if available)
5. **Gate Status Widget**
   - latest `gate_result.txt` (GO/NO-GO)
   - profile used (L1/L2/L3)

## Threshold Overlay
- Warning/Critical bands must match `docs/ops/ALERT_CATALOG_DAY3.json`.
- Burn-rate severity labels must be visible on alert panels.

## Metadata & Ownership
- Default owner: ops-oncall
- Escalation path: service-owner -> engineering-manager -> incident-commander
- Include runbook quick links on dashboard:
  - `runbooks/DEGRADATION_AND_RECOVERY_PLAYBOOK_v1.md`
  - `runbooks/INCIDENT_TRIAGE_MATRIX_v1.md`

## Missing Metric Behavior
- If a primary metric is missing for active traffic, panel must display `Telemetry Gap` status.
- Gate recommendation defaults to NO-GO until metrics recover or manual incident override is approved.

## Contract Safety
This dashboard spec is observational only; no API contract or business logic is altered.

