# Observability Hardening - Day 3

## Goals
Raise Day 3 observability maturity for controlled capacity characterization without changing contracts or business semantics.

## Canonical Signals
1. **Availability**: successful responses / total requests per endpoint.
2. **Latency**: p50, p95, p99 (overall and endpoint-level).
3. **Error rate**: non-2xx responses plus request exceptions.
4. **Saturation proxy**: timeout count and queue/backlog growth signals.

## Day-2 Alignment
Alert thresholds are aligned to Day-2 SLO framing and error-budget policy artifacts:
- `docs/ops/SLI_SLO_ERROR_BUDGET_v1.md`
- `docs/ops/ERROR_BUDGET_POLICY_DAY2.json`

## Burn Rate -> Severity Mapping
- Burn rate < 1.0x: info/observe only
- Burn rate 1.0x - 2.0x: warning (investigate in business hours)
- Burn rate 2.0x - 4.0x: high warning (on-call acknowledgement)
- Burn rate >= 4.0x: critical (incident bridge + rollback consideration)

## Missing Metric Handling (Fail-Safe)
- Missing availability/error signals are treated as unknown-risk and mapped to WARNING.
- Missing latency percentiles for active traffic are treated as telemetry degradation.
- If critical metrics are absent during a suspected incident, default to conservative action:
  1. freeze progression,
  2. run L1 probe,
  3. rollback-first if probe returns NO-GO.

## Runbook Coupling
Each alert must map to:
- `runbooks/DEGRADATION_AND_RECOVERY_PLAYBOOK_v1.md`
- `runbooks/INCIDENT_TRIAGE_MATRIX_v1.md`
- `runbooks/HOTFIX_PROTOCOL_v1.md`

## Contract Safety Assertion
Observability hardening in Day 3 is additive operational scaffolding and does not alter API contracts or business behavior.

