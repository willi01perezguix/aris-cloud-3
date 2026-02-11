# Changelog

## 0.1.0-rc.2 - Sprint 6 Day 6 (Post-merge stabilization)

### Added
- Consolidated release readiness gate script `scripts/release_readiness_gate.py` with blocker-aware summary and checks for smoke, migration safety, security sanity, readiness, and local performance p95 budget.
- Post-merge critical smoke suite in `tests/smoke/test_post_merge_readiness.py` covering auth, stock contract/totals, transfer lifecycle, POS checkout preconditions, reports/exports availability, and idempotency replay checks.
- Dedicated CI workflow `.github/workflows/release-readiness.yml` for PRs to `main` with sqlite and postgres gate runs.

### Changed
- Recovery runbook updated with executable verification flow and rollback verification steps aligned to release readiness gate commands.

### Notes
- No contract-breaking API changes were introduced.
