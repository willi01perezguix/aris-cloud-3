# Internal Alpha Release Package — Sprint 7 Day 7

## Audience
- Internal testers (QA, product, ops, implementation consultants)

## Included scope
- Core App: auth/session shell, effective-permissions gating, stock integration, POS sales, POS cash.
- Control Center: users actions, RBAC/effective-permissions view, settings (variant fields + return policy).
- SDK: deterministic integration/e2e checks with idempotency and error mapping coverage.

## Excluded scope
- No new backend endpoints.
- No contract-breaking API changes.
- No production store rollout in this alpha wave.

## Install / run steps
1. Python env and deps
   - `cd clients/python`
   - `python -m pip install --upgrade pip`
   - `pip install -r requirements.txt`
2. App smoke checks
   - `pytest tests/core_app tests/control_center -q`
3. Sprint closure e2e/integration checks
   - `pytest tests/e2e tests/integration -q`

## Packaging commands
- Dry run (documented + safe preflight)
  - `cd clients/python/packaging`
  - `./build_core.ps1 -DryRun`
  - `./build_control_center.ps1 -DryRun`
- Real build
  - `./build_core.ps1`
  - `./build_control_center.ps1`

## Artifact naming convention
- `aris-core3-alpha-s7d7-<build>`
- `control-center-alpha-s7d7-<build>`

## Known limitations
- Staging-backed E2E is opt-in (`RUN_STAGING_E2E=1`) and depends on environment access.
- Mixed payment UX messaging has a non-blocking wording improvement tracked for Sprint 8.

## Rollback instructions (client rollout)
1. Stop alpha client distribution.
2. Revert to prior signed internal build (`0.1.0-rc.10` baseline).
3. Clear local session caches and restart clients.
4. Confirm auth + stock + POS smoke checks before reopening access.

## Feedback intake and SLA
- Intake channel: internal QA board + release thread.
- Required fields: module, severity, trace_id, repro steps, expected vs actual.
- SLA targets: P0 ≤ 2h, P1 ≤ 1 business day, P2 next sprint planning.
