# Day 6 — Reporte consolidado de validación (unit + smoke)

- Generado: 2026-02-14T19:31:20.956657+00:00
- Alcance: login/session, tenant/store/user con tenant context, idempotencia UI, RBAC UI gating, diagnóstico/export y smoke funcional.

| Suite | Tests | Fallos | Skipped | Tiempo (s) | Evidencia XML |
|---|---:|---:|---:|---:|---|
| validation | 17 | 0 | 0 | 0.238 | `day6_validation_junit.xml` |
| smoke | 3 | 0 | 0 | 0.048 | `day6_smoke_junit.xml` |
| observability | 6 | 0 | 0 | 0.162 | `day6_observability_junit.xml` |
| **TOTAL** | **26** | **0** | **0** | **0.448** | - |

## Resultado
- Estado global: **PASS**.
- Fallos críticos: **0**.

## Comandos ejecutados
- `python -m pytest -q tests/integration/test_login_me_context.py tests/integration/test_login_me_effective_tenant.py tests/integration/test_stores_tenant_scope.py tests/integration/test_users_tenant_scope_and_actions.py tests/integration/test_users_actions_rbac_ui_guard.py tests/unit/test_mutation_attempts.py tests/integration/test_uat_guardrails_and_idempotency.py tests/unit/test_permission_gate.py tests/unit/test_day5_diagnostics_and_context.py tests/unit/test_csv_exporter.py --junitxml=out/day6/day6_validation_junit.xml`
- `python -m pytest -q tests/unit/test_smoke.py tests/unit/test_release_preflight_expectations.py --junitxml=out/day6/day6_smoke_junit.xml`
- `python -m pytest -q tests/unit/test_main_api_diagnostics.py tests/unit/test_observability_log_contract.py tests/unit/test_config_defaults.py --junitxml=out/day6/day6_observability_junit.xml`
