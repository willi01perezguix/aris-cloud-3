# Release Notes Draft — Sprint 8 Day 9 RC Cutover

## Added
- RC readiness document with reproducible test matrix and release decision scaffolding.
- RC validation evidence template for command-level execution capture.
- RC Go/No-Go checklist runbook.
- Cross-platform RC smoke gate scripts (`.sh` and `.ps1`) that publish deterministic evidence under `artifacts/rc/`.
- Manual `workflow_dispatch` release-candidate gate workflow with artifact upload hard-fail on missing evidence.

## Changed
- Changelog updated with Sprint 8 Day 9 RC cutover entry in Keep a Changelog style.
- `.gitignore` updated for transient RC artifact directory.

## Fixed
- N/A (no code-path behavior changes in API/business logic scope).

## Security
- No changes to auth, RBAC policy semantics, tenant scope enforcement, or audit requirements.

## Operational Notes
- Run `scripts/release/rc_smoke_gate.sh` (Linux/macOS shell) or `scripts/release/rc_smoke_gate.ps1` (PowerShell) to generate reproducible RC evidence.
- Artifacts are written to `artifacts/rc/` with command logs and summary status.

## Rollback
- Revert commit(s) for Sprint 8 Day 9 RC documentation/workflow/scripts.
- Disable or skip the manual RC gate workflow if rollback is in progress.
- Re-run baseline readiness gate before reattempting RC cutover.
