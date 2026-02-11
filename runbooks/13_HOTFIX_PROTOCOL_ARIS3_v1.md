# Hotfix Safety Protocol — ARIS3 v1 (Sprint 6 Day 8)

## Purpose
Provide a safe, minimal-change process for post-go-live hotfixes without violating frozen API/flow rules.

## 1) Hotfix Eligibility
### Allowed
- Critical P0/P1 defect fixes with clear customer impact.
- Configuration and threshold adjustments with rollback path.
- Non-breaking correctness fixes that keep frozen rules intact.
- Observability/alerting improvements that do not alter API contracts.

### Not Allowed
- Contract-breaking API changes.
- New feature scope not required for incident mitigation.
- Schema changes lacking backward compatibility and rollback plan.
- Changes that bypass `/actions` flow or idempotency protections.

## 2) Naming Conventions
- **Branch:** `hotfix/<ticket>-<short-description>`
- **PR title:** `Hotfix: <ticket> <impact summary>`
- **Tag (if used):** `0.1.0-rc.3+hotfix.<n>`

## 3) Mandatory Checks Before Merge
1. Scope check confirms frozen rules remain true.
2. Automated checks pass:
   - `pytest -q tests/smoke/test_post_go_live_stability.py`
   - `python scripts/post_go_live_integrity_check.py --strict`
3. Impacted domain regression subset passes (POS/transfers/stock/RBAC as relevant).
4. Rollback command prepared and tested in dry-run path.
5. Incident owner + release owner approval documented.

## 4) Rollback-First Decision Conditions
Choose rollback-first (before patch-forward) when:
- Customer-critical path remains unavailable after initial mitigation.
- Root cause is uncertain and patch confidence is low.
- Data integrity risk is non-trivial (stock totals, transfer state drift, checkout accounting drift).
- Hotfix ETA exceeds agreed incident SLO for restoration.

## 5) Communication Template (internal)
```text
[ARIS3 HOTFIX STATUS]
Ticket: <ID>
Severity: P0/P1/P2
Customer impact: <summary>
Current decision: patch-forward | rollback-first
Change scope: <one-line technical summary>
Frozen rules check: PASS/FAIL
Checks executed:
- smoke: <result>
- integrity: <result>
- targeted regression: <result>
Rollback plan: <command / release tag>
Owner: <name>
Next update (UTC): <time>
```

## 6) Validated Commands
```bash
git checkout -b hotfix/<ticket>-<short-description>
python scripts/hotfix_readiness_check.py
pytest -q tests/smoke/test_post_go_live_stability.py
python scripts/post_go_live_integrity_check.py --strict
```
