# SLI/SLO + Error Budget Policy v1 (Day-2)

## Policy statements
- **No contract drift:** Operational changes must not change API contracts or semantics.
- **Rollback-first for incidents:** If SLO burn is critical, prioritize rollback/stabilization before optimization work.

## SLIs and SLO Targets (initial, conservative)

| SLI | Definition | Measurement window | SLO target |
|---|---|---|---|
| Availability | Successful requests / total requests | rolling 28 days | >= 99.5% |
| Error rate | 5xx responses / total responses | rolling 1 hour and 24 hours | <= 0.5% (1h), <= 0.3% (24h) |
| p95 latency | 95th percentile response latency for core APIs | rolling 1 hour | <= 450 ms |
| p99 latency | 99th percentile response latency for core APIs | rolling 1 hour | <= 900 ms |
| Job success rate | Successful critical jobs / total critical jobs | rolling 24 hours | >= 99.0% |

## Error budget model
For 99.5% monthly availability SLO, allowable unavailability is ~0.5% per 28 days.

- **Monthly budget:** 0.5% error budget (availability + severe error impact)
- **Fast burn warning:** burn-rate >= 2x over 1h
- **Fast burn critical:** burn-rate >= 5x over 1h
- **Sustained burn warning:** burn-rate >= 1x over 6h
- **Sustained burn critical:** burn-rate >= 2x over 6h

## Burn-rate tiers and required actions

| Tier | Trigger | Action |
|---|---|---|
| Tier 0 (Healthy) | Burn-rate < 1x | Normal release cadence |
| Tier 1 (Warning) | >=1x/6h or >=2x/1h | Freeze non-essential changes, assign incident owner |
| Tier 2 (Critical) | >=2x/6h or >=5x/1h | Rollback-first, incident bridge, on-call escalation |
| Tier 3 (Exhausted) | Budget exhausted for window | Change freeze except fixes, daily leadership review |

## Day-2 gate relationship
- Day-2 gate is a pre-release confidence check and does not replace production telemetry.
- A Day-2 NO-GO should block promotion until resolved or explicitly waived by incident commander and product owner.

## Ownership and review cadence
- Service owner: Platform/Ops primary rotation.
- Review: weekly during hypercare, then bi-weekly.
- Versioning: this file and JSON manifests are versioned together as `v1`.
