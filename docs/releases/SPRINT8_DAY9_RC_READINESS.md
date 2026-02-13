# Sprint 8 Day 9 RC Readiness

## Objective
Prepare the Sprint 8 Day 9 release-candidate cutover package with reproducible release evidence while preserving ARIS v1 API and business behavior.

## Contract and Behavior Guardrails
- No endpoint contract drift introduced (paths, parameters, request/response schemas unchanged).
- No business-rule drift introduced (stock, transfers, POS, reports behavior unchanged).
- Idempotency, tenant scope, RBAC, and audit trail expectations remain enforced.
- `GET /aris3/stock` full-table contract remains unchanged.

## Executed Validation Matrix
Run in this exact order:

1. `python -m pytest clients/python/tests/test_packaging_scaffold.py -q`
2. `Push-Location clients/python; python -m pytest tests/test_packaging_scaffold.py -q; Pop-Location`
3. `python -m pytest tests/test_reports_day3_daily_timezone.py::test_reports_daily_timezone_boundary_and_week_span -q -vv`
4. `python -m pytest tests/smoke/test_go_live_validation.py::test_go_live_pos_checkout_and_reports_exports -q -vv`
5. `python -m pytest tests/packaging/test_packaging_scripts_contract.py -q`
6. `python -m pytest tests -q -x --maxfail=1`

## Pass/Fail Summary Template
| Check | Result (PASS/FAIL) | Notes |
| --- | --- | --- |
| Packaging scaffold (repo path) |  |  |
| Packaging scaffold (clients/python cwd) |  |  |
| Reports timezone boundary test |  |  |
| Go-live smoke checkout/reports export |  |  |
| Packaging scripts contract test |  |  |
| Full suite fast-fail gate |  |  |

## Environment Notes
- OS: Linux (CI/local shell compatible)
- Python: `python --version` from execution host
- DB backend(s): SQLite default and/or Postgres when configured via `DATABASE_URL`

## Known Non-Blocking Warnings
- None recorded for this RC readiness package at authoring time.

## Release Decision Inputs
- RC documentation bundle is complete.
- RC smoke gate scripts provide deterministic artifact output under `artifacts/rc/`.
- Manual workflow gate is additive and uploads evidence artifacts on every run.
