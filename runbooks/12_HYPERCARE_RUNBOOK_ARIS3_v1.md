# Hypercare Runbook — ARIS3 v1 (24–72h)

## Objective
Provide structured post-go-live monitoring, fast incident response, and clear release stabilization exit criteria.

## Watch Windows and Owners
| Window | Coverage | Owner | Backup |
|---|---|---|---|
| T+0h to T+8h | Continuous active watch | Release engineer on-call | SRE backup |
| T+8h to T+24h | Business-hour + alert-driven | Product ops + on-call | Engineering manager |
| T+24h to T+72h | Alert-driven watch, 2h health reviews | On-call rotation | Release engineer |

## Core SLIs / SLO Guardrails
- **API error rate (5xx):** target `< 1.0%` per 5-min window.
- **p95 latency (critical APIs):** target `< 350ms` sustained.
- **POS checkout success rate:** target `>= 99.5%`.
- **Transfer action success rate (`/actions`):** target `>= 99.5%`.
- **DB health:** replication lag acceptable, connection saturation `< 80%`, lock wait within baseline.

## Alert Thresholds and Escalation
### P1 (critical)
- Threshold examples:
  - 5xx error rate `>= 5%` for 10 minutes.
  - Checkout success `< 97%` for 10 minutes.
  - Service unavailable / hard down.
- Escalation path:
  1. On-call engineer (immediate)
  2. Incident commander + SRE lead (within 5 min)
  3. Product/Ops owner (within 10 min)

### P2 (high)
- Threshold examples:
  - p95 latency `> 500ms` for 15 minutes.
  - Transfer action success `< 99%` for 15 minutes.
- Escalation path:
  1. On-call engineer (immediate)
  2. Service owner (within 15 min)

### P3 (medium)
- Threshold examples:
  - Non-blocking regressions, minor reporting/export delays.
- Escalation path:
  1. Team channel triage
  2. Next business-cycle patch planning

## Triage Decision Tree (P1 / P2 / P3)
1. **Is customer checkout or transfer blocked?**
   - Yes -> P1
2. **Is service degraded beyond SLO but still functional?**
   - Yes -> P2
3. **Is impact low/non-critical with workaround?**
   - Yes -> P3
4. For P1/P2, evaluate rollback trigger criteria from go-live playbook.

## Incident Logging Template
```
Incident ID:
Severity: P1 / P2 / P3
Start time (UTC):
Detected by:
Current status:
Customer impact summary:
Affected endpoints/flows:
Mitigation actions executed:
Rollback needed? yes/no
Owner:
Next update time:
Resolution time (UTC):
RCA follow-up ticket:
```

## Stabilized Release Exit Criteria (Checklist)
- [ ] No open P1 incidents in last 24h.
- [ ] No unresolved P2 older than agreed SLA.
- [ ] Error rate and latency stable within guardrails for continuous 24h.
- [ ] Checkout and transfer success rates meet targets.
- [ ] No frozen-rule violations observed in monitoring/smoke.
- [ ] Final closure notes published and acknowledged by Engineering + Product/Ops.
