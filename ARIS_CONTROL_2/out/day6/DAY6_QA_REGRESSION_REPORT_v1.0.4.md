# ARIS_CONTROL_2 v1.0.4 — QA integral + regresión (Day 6)

Fecha: 2026-02-14  
Endpoint base objetivo: `https://aris-cloud-3-api-pecul.ondigitalocean.app/`

## 1) Ejecución de suite completa

| Suite | Comando | Resultado | Tiempo | Evidencia |
|---|---|---|---|---|
| Unit (ARIS_CONTROL_2) | `PYTHONPATH=. python -m pytest -q tests/unit --junitxml out/day6/day6_unit_junit_v1_0_4.xml` | PASS (100/100) | 1.05 s | `ARIS_CONTROL_2/out/day6/day6_unit_junit_v1_0_4.xml`, `ARIS_CONTROL_2/out/day6/day6_unit_v1_0_4.log` |
| Integration/UI tests (ARIS_CONTROL_2) | `PYTHONPATH=. python -m pytest -q tests/integration --junitxml out/day6/day6_integration_junit_v1_0_4.xml` | PASS (12/12) | 0.87 s | `ARIS_CONTROL_2/out/day6/day6_integration_junit_v1_0_4.xml`, `ARIS_CONTROL_2/out/day6/day6_integration_v1_0_4.log` |
| Backend regression (ARIS Cloud 3 API) | `python -m pytest -q tests --junitxml out/day6/day6_backend_junit_v1_0_4.xml` | PASS (251/251) | 359.63 s | `out/day6/day6_backend_junit_v1_0_4.xml`, `out/day6/day6_backend_v1_0_4.log` |
| Smoke E2E manual guiado | `pwsh -NoProfile -Command "./scripts/windows/day6_guided_e2e_smoke.ps1"` | BLOCKED (sin `pwsh`) | N/A | consola Day 6 |
| Smoke endpoint remoto | `curl https://aris-cloud-3-api-pecul.ondigitalocean.app/health` | BLOCKED (`CONNECT tunnel failed: 403`) | N/A | consola Day 6 |

## 2) Cobertura de flujos críticos

| Flujo crítico requerido | Cobertura | Estado |
|---|---|---|
| a) Login/sesión | `tests/integration/test_login_me_context.py`, `tests/integration/test_login_me_effective_tenant.py`, `tests/unit/test_day4_session_hardening.py` | PASS |
| b) Tenant context en Stores/Users | `tests/integration/test_stores_tenant_scope.py`, `tests/integration/test_users_tenant_scope_and_actions.py`, `tests/integration/test_tenant_switch_state_reset.py` | PASS |
| c) Acciones admin (`set_status`, `set_role`, `reset_password`) | `tests/integration/test_users_tenant_scope_and_actions.py`, `tests/unit/test_admin_module_mutations_contract.py`, `tests/unit/test_admin_guards_still_hold.py` | PASS |
| d) Manejo de errores (`401/403/409/422/500`) con `code/message/trace_id` | Backend: `tests/test_access_control*.py`, `tests/test_admin_core.py`, `tests/test_reports_exports_day5_observability.py`; App: `tests/unit/test_errors.py`, `tests/unit/test_error_mapper.py`, `tests/unit/test_observability_log_contract.py` | PASS |
| e) Diagnóstico/incidencias/export soporte | `tests/unit/test_day5_diagnostics_and_context.py`, `tests/unit/test_main_api_diagnostics.py`, `tests/unit/test_day5_support_package.py` | PASS |

## 3) Consolidado PASS/FAIL

- Total pruebas automáticas ejecutadas: **363**
- PASS: **363**
- FAIL: **0**
- ERROR: **0**
- SKIP: **0**

## 4) Hallazgos y bloqueos no funcionales

1. **Packaging RC Windows bloqueado por entorno Linux**
   - `pwsh` no disponible.
   - `PyInstaller` no instalado y no descargable en este entorno.
2. **Smoke manual contra endpoint remoto bloqueado por red/proxy CI**
   - `curl` responde `CONNECT tunnel failed, response 403`.

## 5) Veredicto Day 6 (alcance disponible)

- **QA/regresión automatizada: VERDE**.
- **Estado global: PASS CONDICIONAL**, pendiente de ejecutar gates exclusivamente Windows/red release para cerrar RC final.
