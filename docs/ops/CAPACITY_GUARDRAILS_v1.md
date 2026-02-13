# Capacity Guardrails v1 (Post-GA Day 3)

## Non-negotiable Safety Constraints
- No API contract changes.
- No business-rule changes.
- Keep tenant scope, RBAC, idempotency, and audit guarantees intact.
- Keep `GET /aris3/stock` full-table contract unchanged.

## Guardrail Targets
### Hard gates by profile
| Profile | Max p95 (ms) | Max p99 (ms) | Max error rate |
|---|---:|---:|---:|
| L1 | 900 | 1500 | 1.0% |
| L2 | 1100 | 1800 | 1.5% |
| L3 | 1400 | 2200 | 2.0% |

### Conservative envelope rule
- Operate at <= 75% of hard latency gates during steady state.
- Treat any sustained trend > 90% of hard gate as degradation precursor.

## Degradation Triggers
Trigger degradation mode if any condition holds:
- p95 latency breaches profile hard gate for 2 consecutive probe windows.
- Error rate exceeds profile hard gate in any probe window.
- Endpoint availability drops below 99% in probe data.
- Saturation proxy indicates queue growth or rising timeout counts.

## Rollback-First Policy
When a trigger fires:
1. Mark NO-GO and stop progression.
2. Execute rollback to last known good deployment.
3. Validate `/health` and core read paths.
4. Re-run L1 probe and confirm gates before further actions.

## Communication and Accountability
- Incident commander: on-call operations owner.
- Escalation: service owner -> engineering manager -> incident lead.
- Required updates every 15 minutes while customer impact persists.

## No-Contract-Drift Assertion
All guardrails in this file are operational controls only. They do not modify endpoint contracts, payload semantics, or domain behavior.

