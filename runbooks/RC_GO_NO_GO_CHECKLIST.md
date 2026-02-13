# RC Go/No-Go Checklist (Sprint 8 Day 9)

## Scope and Non-Goals
- Scope: RC evidence reproducibility, release note hygiene, manual gate execution confidence.
- Non-goals: API contract updates, business-rule changes, broad refactors.

## Pre-Flight
- [ ] Working tree clean (except intended RC files)
- [ ] Dependencies installed and test environment prepared
- [ ] `DATABASE_URL` verified for selected backend

## Contract/Behavior Safety
- [ ] Confirm no endpoint path/param/schema changes
- [ ] Confirm no stock/transfers/POS/reports rule changes
- [ ] Confirm idempotency, tenant scope, RBAC, and audit guarantees unchanged
- [ ] Confirm `GET /aris3/stock` full-table contract untouched

## Required Validation Commands
- [ ] `python -m pytest clients/python/tests/test_packaging_scaffold.py -q`
- [ ] `Push-Location clients/python; python -m pytest tests/test_packaging_scaffold.py -q; Pop-Location`
- [ ] `python -m pytest tests/test_reports_day3_daily_timezone.py::test_reports_daily_timezone_boundary_and_week_span -q -vv`
- [ ] `python -m pytest tests/smoke/test_go_live_validation.py::test_go_live_pos_checkout_and_reports_exports -q -vv`
- [ ] `python -m pytest tests/packaging/test_packaging_scripts_contract.py -q`
- [ ] `python -m pytest tests -q -x --maxfail=1`

## Evidence
- [ ] `artifacts/rc/summary.txt` generated
- [ ] `artifacts/rc/commands.log` generated
- [ ] `docs/releases/RC_VALIDATION_EVIDENCE.md` updated with actual outputs

## GO/NO-GO Decision
- [ ] GO if all required tests pass and no drift detected
- [ ] NO-GO if any required test fails or drift is detected

## Rollback Rehearsal
1. Revert Sprint 8 Day 9 RC cutover commit(s).
2. Validate working tree and re-run baseline readiness checks.
3. Confirm prior release workflow behavior remains intact.
4. Re-open RC effort only after blocker root cause and mitigation are documented.
