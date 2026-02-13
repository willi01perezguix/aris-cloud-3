# Alert Thresholds and Escalation v1 (Day-2)

## Guardrail policies
- **No contract drift:** alerts and ops automation must not alter API contract behavior.
- **Rollback-first incidents:** for Sev-1/Sev-2 reliability incidents, rollback to last known good state first.

## Thresholds

| Signal | Warning threshold | Critical threshold |
|---|---|---|
| Availability (1h) | < 99.7% | < 99.5% |
| Error rate (5xx, 15m) | > 0.5% | > 1.0% |
| p95 latency (15m) | > 450 ms | > 700 ms |
| p99 latency (15m) | > 900 ms | > 1200 ms |
| Job success rate (24h) | < 99.0% | < 97.5% |
| Error budget burn (1h) | >= 2x | >= 5x |
| Error budget burn (6h) | >= 1x | >= 2x |

## Escalation matrix

| Severity | Trigger examples | Initial response | Escalation path | SLA |
|---|---|---|---|---|
| Sev-3 | Warning threshold breach, no user-visible outage | Triage in ops queue, assign owner | Primary on-call | Acknowledge <= 30m |
| Sev-2 | Critical threshold breach with partial impact | Open incident channel, start mitigation | Primary + Secondary on-call, Eng manager | Acknowledge <= 15m |
| Sev-1 | Multi-tenant outage, data risk, budget exhaustion trend | Rollback-first, incident commander, comms | Full on-call tree + leadership | Acknowledge <= 5m |

## Standard actions by severity
1. Confirm tenant scope and RBAC boundaries remain intact.
2. Validate idempotency and audit trails unaffected.
3. Mitigate impact (rollback-first for Sev-1/Sev-2).
4. Capture timeline and artifact links.
5. Open follow-up tasks for prevention.

## Communication template
- Status: `Investigating | Mitigating | Monitoring | Resolved`
- Impact: `% requests impacted`, affected tenants/modules
- Decision: `rollback`, `forward fix`, or `partial feature freeze`
- Next update ETA
