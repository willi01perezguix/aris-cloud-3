# SLI/SLO Baseline Lock — Sprint 6 Day 8

## Baseline Indicators
| Indicator | Definition | Target SLO | Measurement Window |
|---|---|---|---|
| API error rate | Percentage of 5xx responses on core ARIS3 endpoints | < 1.0% | 5-minute rolling |
| p95 latency | p95 latency for critical APIs (`/aris3/stock`, `/aris3/transfers/*/actions`, `/aris3/pos/sales/*/actions`) | < 350ms sustained | 15-minute rolling |
| Checkout success rate | Successful checkout actions / total checkout attempts | >= 99.5% | 15-minute rolling |
| Transfer action success rate | Successful transfer action mutations / total transfer action requests | >= 99.5% | 15-minute rolling |
| DB connectivity health | DB availability, connection saturation, lock wait sanity | availability 99.9%; saturation < 80% | 5-minute rolling |

## Alert Thresholds and Severities
| Severity | Trigger |
|---|---|
| P1 | 5xx >= 5% for 10 minutes; checkout success < 97% for 10 minutes; sustained service unavailability |
| P2 | p95 > 500ms for 15 minutes; transfer success < 99% for 15 minutes; DB saturation >= 90% |
| P3 | Non-critical endpoint degradation, delayed exports/reports, warning-level drift |

## Escalation Policy References
- Operational response sequencing: `runbooks/12_HYPERCARE_RUNBOOK_ARIS3_v1.md`
- Rollback trigger and execution flow: `runbooks/11_GO_LIVE_PLAYBOOK_ARIS3_v1.md`
- Recovery and restore verification: `runbooks/10_RECOVERY_PLAYBOOK_ARIS3_v1.md`
- Hotfix governance: `runbooks/13_HOTFIX_PROTOCOL_ARIS3_v1.md`

## Hypercare Exit Criteria (Steady-State Gate)
All conditions must be true for a continuous 24h window:
1. No open P0 or P1 incidents.
2. No unresolved P2 older than agreed SLA.
3. Error rate and p95 latency stay inside SLO targets.
4. Checkout and transfer action success rates remain above thresholds.
5. Integrity checks pass with no critical failures.
6. Release closure package accepted by Engineering + Product/Ops.

## Day 8 Lock Decision
- Baseline **locked** for post-go-live period.
- Recommendation remains controlled by final closure artifact in `docs/releases/FINAL_RELEASE_CLOSURE_S6D8.md`.
