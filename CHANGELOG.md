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

## 0.1.0-rc.3 - Sprint 6 Day 7 (RC sign-off, go-live, hypercare)

### Added
- RC final sign-off package: `docs/releases/RC_FINAL_SIGNOFF_S6D7.md`.
- Go/No-Go decision checklist: `docs/releases/GO_NO_GO_CHECKLIST_S6D7.md`.
- Controlled go-live playbook with staged deployment, rollback triggers, rollback execution, and communication templates: `runbooks/11_GO_LIVE_PLAYBOOK_ARIS3_v1.md`.
- Hypercare runbook with SLI/SLO guardrails, escalation paths, triage tree, and stabilization exit criteria: `runbooks/12_HYPERCARE_RUNBOOK_ARIS3_v1.md`.
- Day 7 post-deploy smoke validation suite: `tests/smoke/test_go_live_validation.py`.
- Optional preflight automation command: `scripts/go_live_checklist.py`.
- Final release notes artifact: `docs/releases/RELEASE_NOTES_S6D7.md`.

### Changed
- Release-readiness CI workflow now runs Day 7 go-live smoke validation in both sqlite and postgres jobs.

### Notes
- No contract-breaking API changes were introduced.
