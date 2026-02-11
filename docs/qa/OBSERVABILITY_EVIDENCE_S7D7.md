# Observability Evidence — Sprint 7 Day 7

This document maps closure tests to traceable evidence fields.

## Required evidence fields
- `trace_id`
- `module`
- `action`
- `status_code`
- timing summary (`duration_ms`)

## Evidence sources
1. Deterministic cross-module E2E test
   - File: `clients/python/tests/e2e/test_sprint7_day7_cross_module.py`
   - Captures module/action/status/timing rows in `RequestAudit.rows`.
2. Integration error mapping suite
   - File: `clients/python/tests/integration/test_sprint7_day7_integration.py`
   - Captures trace propagation for 403/409/transport paths.
3. CI artifacts
   - Workflow: `.github/workflows/sprint7-day7-e2e-uat.yml`
   - Uploads `sprint7-day7-test-report.xml` and `sprint7-day7-summary.txt`.

## Operator guidance
When triaging defects, include:
- failing case ID from E2E/UAT matrix,
- trace_id from API/error payload,
- linked CI artifact name and run URL.
