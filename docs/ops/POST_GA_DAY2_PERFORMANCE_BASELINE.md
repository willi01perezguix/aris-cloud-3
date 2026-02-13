# Post-GA Day 2 Performance Baseline

## Purpose
This baseline defines a reproducible Day-2 operational gate for performance and reliability after GA.

## Guardrails
- **No contract drift:** API paths, parameters, and response schemas remain unchanged.
- **No business-rule drift:** stock, transfers, POS, and reporting semantics are unchanged.
- **Rollback-first incidents:** if any Day-2 gate check fails in production workflows, pause rollout and roll back before optimization.

## Baseline Measurement Scope
The Day-2 gate executes a fixed command matrix and records deterministic artifacts under `artifacts/post-ga/day2/`.

### Required command matrix
1. `python -m pytest clients/python/tests/test_packaging_scaffold.py -q`
2. `Push-Location clients/python; python -m pytest tests/test_packaging_scaffold.py -q; Pop-Location`
3. `python -m pytest tests/test_reports_day3_daily_timezone.py::test_reports_daily_timezone_boundary_and_week_span -q -vv`
4. `python -m pytest tests/smoke/test_go_live_validation.py::test_go_live_pos_checkout_and_reports_exports -q -vv`
5. `python -m pytest tests/packaging/test_packaging_scripts_contract.py -q`
6. Optional: `python -m pytest tests -q -x --maxfail=1`

## Initial Day-2 Baseline (v1)
Conservative initial values to avoid false confidence while enabling early signal.

| SLI | Baseline source | Baseline v1 |
|---|---|---|
| Availability | Day-2 gate pass ratio (required checks) | 100% required checks pass for GO |
| Error rate | Failed checks / total required checks | 0% for GO, >0% is NO-GO |
| API p95 latency | Most recent production telemetry snapshot | `<= 450 ms` |
| API p99 latency | Most recent production telemetry snapshot | `<= 900 ms` |
| Job success rate | Scheduled critical jobs (exports/backups/integrity) | `>= 99.0%` over rolling 24h |

## Artifact Contract
Day-2 artifacts include:
- `metadata.json` (git SHA, UTC timestamp, python version, platform)
- `command_matrix.json` (ordered checks)
- `results.json` (pass/fail per check + durations)
- `pytest_durations_summary.json` (slowest tests extracted from pytest output)
- `summary.txt` (concise GO/NO-GO output)

## GO / NO-GO Rule
- **GO:** all required checks pass and no critical threshold breach.
- **NO-GO:** any required check fails or any critical threshold breach is detected.

## Operational Notes
- This baseline is intended as a **safe first operational contract**, not a final performance tuning target.
- Thresholds and budgets are formalized in:
  - `docs/ops/SLI_SLO_ERROR_BUDGET_v1.md`
  - `runbooks/ALERT_THRESHOLDS_AND_ESCALATION_v1.md`
