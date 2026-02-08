# Sprint 1 Closeout

## Summary of Days 1–7
- Day 1: Project bootstrap, Alembic scaffolding, base CI workflow.
- Day 2: Database foundation, initial migration, seed baseline.
- Day 3: Auth flow with JWT, must-change-password flow.
- Day 4: Tenant/store/user scope guards and request context wiring.
- Day 5: RBAC evaluator with effective permissions baseline.
- Day 6: Idempotency handling, audit events base, error catalog hardening.
- Day 7: Integration validation, CI hardening, operational hardening, and release-readiness docs.

## Accepted Constraints / Non-Goals
- No new business modules (stock/transfers/pos) in Sprint 1.
- No architecture redesign; /aris3 structure stays intact.
- No breaking API contract changes unless required for safety/compliance.

## Known Risks & Technical Debt
- CI uses SQLite for deterministic tests; Postgres parity relies on schema discipline and should be re-validated during Sprint 2.
- Authorization/rbac coverage focuses on baseline permissions; finer-grained policy expansion remains open.
- Seed data is minimal and assumes single default tenant/store; multi-tenant seed variants may be needed.

## Rollback Notes
- Rollback application to pre-Day 7 state by reverting the Sprint 1 Day 7 commit and redeploying the prior image.
- For DB rollback, downgrade Alembic to the previous revision and restore the prior database snapshot.

## Sprint 2 Recommended Starting Point
- Add Postgres integration tests in CI alongside SQLite.
- Expand RBAC policy coverage and introduce tenant-specific permission overrides.
- Add observability baseline: structured log formatting + trace/span propagation to external systems.

## Sprint 1 Acceptance Checklist
| Area | Status | Notes |
| --- | --- | --- |
| Auth | Pass | Login/change-password validated via tests. |
| Scope enforcement | Pass | Tenant/store/user scope guards covered. |
| RBAC baseline | Pass | Effective permissions response validated. |
| Idempotency | Pass | Replay and conflict paths validated. |
| Audit events | Pass | Change-password audit event captured. |
| CI green | Pass | Import check, tests, and Alembic sanity steps required. |
