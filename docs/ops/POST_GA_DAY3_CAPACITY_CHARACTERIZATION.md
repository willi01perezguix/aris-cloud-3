# POST-GA Day 3 Capacity Characterization

## Purpose
This document defines a controlled, repeatable load characterization approach for post-GA Day 3 hardening, with a strict focus on operational understanding and guardrails.

## No-Contract-Drift Statement
This Day 3 package is additive-only and does **not** alter API paths, query parameters, request/response schemas, or business behavior. In particular, the full-table contract for `GET /aris3/stock` remains unchanged.

## Scope
### In scope
- Read-heavy probe characterization against:
  - `GET /health`
  - `GET /aris3/stock` with a minimal, read-only query shape
  - `GET /aris3/reports/overview` using a small date window
- Latency and error-shape capture for controlled tiers (L1/L2/L3)
- Artifact generation for reproducibility under `artifacts/post-ga/day3/`
- GO/NO-GO gating based on conservative operational thresholds

### Out of scope
- Endurance/soak tests
- Write-path stress (stock transfers, POS mutations, exports generation)
- Multi-region/network-chaos experiments
- Any interpretation that changes tenant scope, RBAC, idempotency, or audit guarantees

## Controlled Load Profiles
| Profile | Intended use | Iterations | Concurrency | Warmup | Timeout (s) |
|---|---|---:|---:|---:|---:|
| L1 | Safe baseline probe | 24 | 2 | 3 | 5 |
| L2 | Moderate verification | 48 | 4 | 4 | 5 |
| L3 | Pre-incident envelope check | 72 | 6 | 6 | 5 |

Notes:
- Each iteration executes the same endpoint set for deterministic timing series.
- Warmup requests are excluded from reported timing statistics.

## Measurement Method
- Single-run deterministic probe script with explicit CLI overrides.
- Per-request timing captured in milliseconds in `timings.csv`.
- Summary statistics (availability, p50/p95/p99, error rate) written to `summary.json`.
- Environment fingerprint written to `env_snapshot.json` (git SHA, UTC timestamp, Python, platform).

## Conservative Operating Envelope
Baseline envelope policy:
- Target operating band: p95 latency under profile threshold with error rate at/under threshold.
- Headroom policy: keep at least 25% latency headroom versus the profile hard gate during normal operations.
- If p95 enters the final 10% of threshold or error rate trends upward, treat as pre-degradation warning and reduce concurrent background activity before customer impact.

## Decision Policy (Rollback First)
- Primary rule: rollback-first over tuning-in-place for uncertain degradations.
- If hard gate fails in strict mode, mark NO-GO and stop promotion.
- Recovery actions:
  1. Halt progressive rollout.
  2. Revert to last known good deployment.
  3. Confirm health and error-budget recovery.
  4. Re-run L1 characterization before any retry.

## Incident Communication Checklist
- Incident title, start time (UTC), impacted tier/profile
- Customer-visible symptoms and affected endpoints
- Current gate status: GO/NO-GO and failing metric(s)
- Immediate mitigation taken (rollback, traffic reduction, feature containment)
- Owner on point + next update time
- Exit criteria for recovery and verification steps

## Evidence Package
- `artifacts/post-ga/day3/env_snapshot.json`
- `artifacts/post-ga/day3/timings.csv`
- `artifacts/post-ga/day3/summary.json`
- `artifacts/post-ga/day3/gate_result.txt`

