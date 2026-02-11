# Controlled Go-Live Playbook — ARIS3 v1 (Sprint 6 Day 7)

## Objective
Execute a controlled production go-live with explicit safety checks, rollback triggers, and concise communication.

## Scope and Safety
- No contract-breaking API changes allowed.
- Frozen rules remain in force:
  - `GET /aris3/stock` full-table contract (`meta/rows/totals`).
  - Mutations for transitions only through `/actions` endpoints.
  - `TOTAL = RFID + PENDING` on sellable locations.
  - `IN_TRANSIT` remains logistic-only, non-sellable.
  - POS sales behavior unchanged (`EPC -> RFID`, `SKU -> PENDING`, no fallback in v1).
  - Idempotency and transaction safety unchanged.

## Dry-run Mode (for non-prod environments)
If this environment cannot deploy to production directly, operators must run dry-run commands first:

```bash
python scripts/go_live_checklist.py --dry-run
```

Expected output example:
```text
Go-Live Checklist Summary
...
release-gate:day6 ... DRY-RUN python scripts/release_readiness_gate.py --pytest-target tests/smoke/test_post_merge_readiness.py
smoke:go-live-day7 ... DRY-RUN pytest -q tests/smoke/test_go_live_validation.py
...
Go-live checklist result: DRY-RUN
```

---

## 1) Pre-deploy checks (must all pass)
1. Confirm working branch and local status:
   ```bash
   git branch --show-current
   git status --short
   ```
2. Validate consolidated preflight:
   ```bash
   python scripts/go_live_checklist.py
   ```
3. Confirm last backup and restore drill references (from recovery playbook):
   ```bash
   python scripts/ops/backup_create.py --name pre_go_live_YYYYMMDD_HHMM
   python scripts/ops/backup_manifest_validate.py <manifest_path>
   ```
4. Verify staging parity and no open blocker incidents.

## 2) Deploy steps (staged / canary)
1. Announce deployment start in ops channel.
2. Deploy to canary subset (or one instance/one AZ):
   ```bash
   # Operator-owned deploy command (example)
   ./deploy.sh --env prod --strategy canary --batch 10
   ```
3. Wait 5–10 minutes and monitor errors/latency.
4. If healthy, continue rollout:
   ```bash
   ./deploy.sh --env prod --strategy rolling --batch 25
   ```
5. Complete rollout:
   ```bash
   ./deploy.sh --env prod --strategy rolling --batch 100
   ```

## 3) Immediate post-deploy verification
1. Health/readiness:
   ```bash
   curl -sS https://<prod-host>/health
   curl -sS https://<prod-host>/ready
   ```
2. Critical smoke in deployed env:
   ```bash
   pytest -q tests/smoke/test_go_live_validation.py
   ```
3. Quick contract checks:
   ```bash
   curl -sS https://<prod-host>/aris3/stock
   curl -sS https://<prod-host>/aris3/reports/overview
   curl -sS https://<prod-host>/aris3/exports
   ```

## 4) Abort / rollback triggers
Trigger immediate rollback when any condition is met:
- `/health` or `/ready` returns non-200 for > 2 consecutive checks.
- Critical smoke fails in auth, stock invariants, transfer actions, POS checkout, or reports/exports.
- Error rate exceeds hypercare threshold for 10+ minutes.
- p95 latency breaches threshold for 15+ minutes.
- Data integrity signals indicate frozen-rule drift.

## 5) Rollback execution + verification
1. Announce rollback start.
2. Revert application to previous stable release:
   ```bash
   ./deploy.sh --env prod --rollback --to <previous_release_tag>
   ```
3. Restore data if required (only after incident lead approval):
   ```bash
   python scripts/ops/backup_restore_verify.py <manifest_path>
   ```
4. Verify rollback health and smoke:
   ```bash
   curl -sS https://<prod-host>/health
   curl -sS https://<prod-host>/ready
   pytest -q tests/smoke/test_go_live_validation.py
   ```

## 6) Communication templates
### A) Deployment start
> `ARIS3 release RC.3 started (canary phase). Decision owner: <name>. Next update in 10 min.`

### B) Canary success
> `ARIS3 canary healthy (error/latency within guardrails). Proceeding to rolling rollout 25% -> 100%.`

### C) Go-live complete
> `ARIS3 release RC.3 go-live complete. Post-deploy smoke passed. Hypercare window now active (T+72h).`

### D) Abort / rollback
> `ARIS3 rollout aborted due to <reason>. Rollback in progress to <previous_release_tag>. Next status in 10 min.`
