# Hotfix Changelog

> Operational ledger for post-GA emergency changes. Every entry must include root cause, blast radius, contract drift check, rollback path, test evidence, and postmortem actions.

## Entry Template
### YYYY-MM-DD HH:MM UTC — `<hotfix-id>`
- **Severity**: SEVx
- **Root cause**:
- **Blast radius**:
- **Contract drift check**: PASS/FAIL (details)
- **Mitigation path**: rollback-first / forward-fix
- **Rollback command path**:
- **Tests run (evidence)**:
- **Result**: GO / NO-GO
- **Postmortem actions**:
  - `<owner> — <date> — <action>`

## Entries

### 2026-01-15 18:00 UTC — `api-contract-hardening-admin-auth`
- **Severity**: SEV2
- **Root cause**: inconsistencias de contrato (errores, scoping superadmin, probes de salud) detectadas en auditoría backend.
- **Blast radius**: endpoints auth/admin y documentación OpenAPI.
- **Contract drift check**: PASS (se mantiene compatibilidad con alias/deprecated).
- **Mitigation path**: forward-fix
- **Rollback command path**: revert commit del hardening y redeploy.
- **Tests run (evidence)**: `pytest -q tests/test_admin_auth_contract_hardening.py tests/test_health.py tests/test_ready.py tests/test_openapi_admin_list_filters.py`
- **Result**: GO
- **Postmortem actions**:
  - Backend TL — 2026-02-01 — remover alias/deprecated inputs al llegar sunset (`2026-06-30`).

