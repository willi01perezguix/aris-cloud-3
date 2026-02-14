# ARIS_CONTROL_2 v1.0.3 — QA integral + regresión (Day 6)

Fecha: 2026-02-14
Endpoint validado por defecto: `https://aris-cloud-3-api-pecul.ondigitalocean.app/`

## 1) Ejecución de suite completa (alcance disponible en este entorno)

| Suite | Comando | Resultado | Tiempo (s) | Evidencia |
|---|---|---|---:|---|
| Unit + Integration (desktop app) | `python -m pytest -q tests/unit tests/integration --junitxml=out/day6/day6_pytest_full_junit.xml` | PASS (95/95) | 0.977 | `ARIS_CONTROL_2/out/day6/day6_pytest_full_junit.xml` |
| Integration/UI-ish (SDK control center) | `python -m pytest -q tests/control_center tests/integration tests/test_release_hardening.py --junitxml=artifacts/qa/day6_clients_pytest_junit.xml` | PASS (21/21) | 3.751 | `clients/python/artifacts/qa/day6_clients_pytest_junit.xml` |
| Smoke guiado (scaffold API) | `python clients/python/tools/qa_matrix_runner.py --quick --fail-on none` | PASS con SKIP esperados por credenciales no disponibles | n/a | `artifacts/qa/client_qa_matrix_20260214T205952Z.{json,md}` |

## 2) Cobertura de flujos críticos solicitados

| Flujo crítico | Evidencia | Estado |
|---|---|---|
| a) login/sesión | pruebas de login/me y guardas de sesión (`test_login_me_context.py`, `test_login_me_effective_tenant.py`, `test_day4_session_hardening.py`) | PASS |
| b) tenant context (Stores/Users) | `test_stores_tenant_scope.py`, `test_users_tenant_scope_and_actions.py`, `test_tenant_switch_state_reset.py` | PASS |
| c) admin actions (`set_status`, `set_role`, `reset_password`) | `test_users_tenant_scope_and_actions.py`, `test_admin_module_mutations_contract.py`, `test_admin_guards_still_hold.py` | PASS |
| d) manejo 401/403 + restore contexto | `test_day4_session_hardening.py`, `test_retry_timeout_behavior.py`, `test_users_actions_rbac_ui_guard.py` | PASS |
| e) diagnóstico/conectividad | `test_day5_diagnostics_and_context.py`, `test_main_api_diagnostics.py`, `test_observability_log_contract.py` | PASS |

## 3) Matriz de regresión v1.0.2 -> v1.0.3

| Área | Verificación | Estado | Comentarios |
|---|---|---|---|
| Flujo base Tenant/Store/User | listados + acciones admin + scope por tenant | PASS | Sin cambio de contrato API; validado por integración.
| RBAC visual | acciones permitidas/no permitidas en UI | PASS | Guardrails conservados.
| Idempotencia UI anti-doble-submit | validación de mutation attempts e idempotency keys | PASS | Cobertura por unit/integration.
| Persistencia de filtros/tenant/paginación | refresh y restore de contexto | PASS | Se actualizó test legacy para firma actual de `_run_listing_loop`.

### Diferencias esperadas (mejoras)
- Fortalecida sanitización de variables sensibles en export de soporte (`ARIS3_*` con marcadores de secreto se redacan explícitamente).
- Actualización de versión mostrada en panel/diagnóstico a `v1.0.3-rc`.

### Diferencias no esperadas (bugs)
- No se detectaron regressions bloqueantes en el alcance ejecutado.

## 4) Smoke E2E manual guiado (operativo en este entorno)

- Arranque de app CLI validado con salida limpia (`python -m aris_control_2.app.main`, opción `5 Exit`).
- Login real/acciones contra tenant productivo: **BLOCKED** por no disponer de credenciales operativas en entorno CI.
- QA matrix dejó trazabilidad de escenarios `PASS/SKIP` para ejecución reproducible en entorno con credenciales.

## 5) Estado consolidado

- **Resultado global Day 6 (scope CI Linux): PASS CONDICIONAL**.
- Fallos críticos: **0**.
- Bloqueadores de release final: packaging Windows `.exe` + smoke de arranque real en host Windows release.
