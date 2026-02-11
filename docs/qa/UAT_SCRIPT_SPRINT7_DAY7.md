# UAT Script — Sprint 7 Day 7

## Execution metadata
- Window: Sprint 7 Day 7 closure window
- Product: ARIS-CORE-3 Core App + Control Center
- Actors: Internal tester, store operator, tenant admin

## Pass/Fail checklist
Use `[ ] Pass` / `[ ] Fail` and record evidence screenshot/log path per case.

### Core App operator flow
1. **UAT-CORE-01 Auth + bootstrap**
   - Steps: login, load profile (`/me`), verify module navigation, logout.
   - Expected: session initialized, user shown, unauthorized modules hidden by default deny.
   - Result: [ ] Pass [ ] Fail
   - Evidence:

2. **UAT-CORE-02 Stock table + filters + totals**
   - Steps: open stock page, filter by SKU/location/pool.
   - Expected: full-table output rendered (`meta/rows/totals`), total obeys `RFID + PENDING`.
   - Result: [ ] Pass [ ] Fail
   - Evidence:

3. **UAT-CORE-03 Import EPC + SKU validation**
   - Steps: submit invalid EPC/SKU payloads, then valid payloads.
   - Expected: validation shown on invalid; success on valid with traceable operation metadata.
   - Result: [ ] Pass [ ] Fail
   - Evidence:

4. **UAT-CORE-04 Migrate SKU→EPC invariant**
   - Steps: run migration for a valid line.
   - Expected: expected effect text and invariant observed (`PENDING -1`, `RFID +1`, `TOTAL unchanged`).
   - Result: [ ] Pass [ ] Fail
   - Evidence:

5. **UAT-CORE-05 POS sales lifecycle + payments**
   - Steps: create draft, edit, checkout (CASH/CARD/TRANSFER), cancel another draft.
   - Expected: transitions only via `/actions`; payment rule requirements enforced.
   - Result: [ ] Pass [ ] Fail
   - Evidence:

6. **UAT-CORE-06 CASH precondition**
   - Steps: attempt CASH checkout without open cash session; open session; retry.
   - Expected: blocked then allowed after open session.
   - Result: [ ] Pass [ ] Fail
   - Evidence:

### Control Center operator flow
7. **UAT-CC-01 Users actions**
   - Steps: perform `set_status`, `set_role`, `reset_password`.
   - Expected: action feedback shown and trace metadata available.
   - Result: [ ] Pass [ ] Fail
   - Evidence:

8. **UAT-CC-02 RBAC precedence + tenant/admin ceiling**
   - Steps: preview effective permissions; attempt blocked admin-ceiling grant.
   - Expected: DENY>ALLOW visualized, blocked grant rejected.
   - Result: [ ] Pass [ ] Fail
   - Evidence:

9. **UAT-CC-03 Settings update**
   - Steps: edit variant fields and return policy settings.
   - Expected: invalid data blocked, valid changes saved.
   - Result: [ ] Pass [ ] Fail
   - Evidence:

## Defect logging template
- Defect ID:
- Title:
- Severity: P0 / P1 / P2
- Module: Core App / Control Center / SDK / CI
- Environment:
- Repro steps:
- Expected result:
- Actual result:
- Trace ID / logs:
- Owner:
- Status: New / Triaged / In Progress / Fixed / Deferred
- Target fix window:
