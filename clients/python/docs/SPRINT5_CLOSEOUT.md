# Sprint 5 Client Closeout

## Done in Sprint 5
- SDK foundations: config, auth/session, HTTP transport, error mapping, tracing, idempotency.
- Domain clients and workflows: Stock, POS Sales, POS Cash, Transfers, and Inventory Counts.
- ARIS CORE 3 shell now includes permission-aware screens for all Sprint 5 modules, including Inventory Counts lifecycle + scan batch.
- CLI smoke scripts now cover inventory count lifecycle actions, scanning, summary/differences, and export contract probing.
- Tests include validation, idempotency wiring, state guards, mocked integration lifecycles, and UI smoke coverage.

## Remaining for Sprint 6
- Richer Inventory Counts UX (full tabbed history/detail grid + pagination and filtering).
- Reporting polish and export download UX integration.
- Packaging/installer and distribution workflows.
- End-to-end environment test suites against staging.

## Known limitations
- Inventory export endpoint is contract-optional; smoke script gracefully reports when unavailable.
- UI currently refreshes detail and status after mutations, but does not yet persist local queued scan batches.
- Final backend-specific labels/messages may need copy adjustments once product wording is finalized.

## Recommended next priorities
1. Add richer count detail grids and scan history UX for store teams.
2. Add staging contract tests for inventory count lock/transition edge cases.
3. Package app shells and smoke utilities for pilot rollout.
