# Sprint 8 Day 10 GA Readiness (Final)

## GA Scope
- Final release-readiness package for Sprint 8 closure from the current `main` readiness baseline.
- GA gate automation additions (`ga-release-gate` workflow and GA gate scripts).
- Operational handoff runbook and release manifest for controlled tagging/release.
- Documentation-only release finalization; no API/business behavior changes.

## Guardrail Confirmation
- **No contract drift:** API paths, params, request/response schemas remain unchanged.
- **No business-rule drift:** stock, transfers, POS, and reports behavior remain unchanged.
- Idempotency, tenant scope, RBAC, and audit semantics are preserved.
- `GET /aris3/stock` full-table contract remains unchanged.

## Validation Matrix (Authoritative)
1. `python -m pytest clients/python/tests/test_packaging_scaffold.py -q`
2. `Push-Location clients/python; python -m pytest tests/test_packaging_scaffold.py -q; Pop-Location`
3. `python -m pytest tests/test_reports_day3_daily_timezone.py::test_reports_daily_timezone_boundary_and_week_span -q -vv`
4. `python -m pytest tests/smoke/test_go_live_validation.py::test_go_live_pos_checkout_and_reports_exports -q -vv`
5. `python -m pytest tests/packaging/test_packaging_scripts_contract.py -q`
6. `python -m pytest tests -q -x --maxfail=1`

## Non-Blocking Warnings
- PowerShell command execution may be unavailable on Linux runners without `pwsh`; bash-equivalent path validation is retained in GA scripts.

## GA Decision
- Recommendation: **GO** when the full validation matrix passes and no contract/business drift is detected.
