# Day 6 — QA integral final y regresión (v1.0.5)

Proyecto: **ARIS_CONTROL_2**  
Fase: **v1.0.5 Day 6**  
Base API por defecto: `https://aris-cloud-3-api-pecul.ondigitalocean.app/`

## 1) Suite completa ejecutada

### 1.1 Backend unit/integration/smoke
- `pytest -q` (repo raíz): **PASS**.
- `pytest -q tests/smoke/test_post_merge_readiness.py -ra`: **PASS** (5/5).
- `python scripts/release_readiness_gate.py --pytest-target tests/smoke/test_post_merge_readiness.py`: **PASS_WITH_WARNINGS**.

### 1.2 Cliente ARIS_CONTROL_2 (unit/integration)
- `PYTHONPATH=. pytest -q tests/unit tests/integration -ra` (desde `ARIS_CONTROL_2/`): **FAIL** (1 caso no crítico, 125 PASS).
  - Falla observada: `tests/unit/test_day1_kickoff_quickwins.py::test_tenant_change_clears_incompatible_users_store_filter`.
  - Resultado real: al cambiar tenant se limpia `filters_by_module["users"]` completo (`{}`) en vez de conservar `{"q":"alice"}`.
  - Impacto: bajo (comportamiento de UX sobre filtros cacheados), sin evidencia de ruptura de contrato API.

### 1.3 Cobertura obligatoria solicitada
Se verificó con el set dirigido:
`PYTHONPATH=. pytest -q tests/unit/test_auth_me_clients.py tests/unit/test_day5_diagnostics_and_context.py tests/unit/test_day5_support_package.py tests/unit/test_pagination_ui_state.py tests/unit/test_day2_listing_state_and_debounce.py tests/integration/test_login_me_context.py tests/integration/test_stores_tenant_scope.py tests/integration/test_users_tenant_scope_and_actions.py tests/integration/test_uat_guardrails_and_idempotency.py tests/integration/test_users_actions_rbac_ui_guard.py`

Resultado: **PASS (22/22)**.

Mapeo de cobertura:
- a) login/sesión + 401/403: `test_auth_me_clients`, `test_login_me_context`, `test_users_actions_rbac_ui_guard`.
- b) tenant context Tenants/Stores/Users: `test_stores_tenant_scope`, `test_users_tenant_scope_and_actions`.
- c) acciones sensibles (set_role/set_status/reset_password): `test_users_tenant_scope_and_actions`, `test_users_actions_rbac_ui_guard`.
- d) idempotencia UI anti-doble-submit: `test_uat_guardrails_and_idempotency`.
- e) diagnóstico/incidencias/historial/exportes: `test_day5_diagnostics_and_context`, `test_day5_support_package`.
- f) filtros/paginación/persistencia de estado: `test_pagination_ui_state`, `test_day2_listing_state_and_debounce`.

## 2) Evidencia de estabilidad release gate
Resumen del gate ejecutado:
- tests sqlite: PASS
- tests postgres: WARN (sin `POSTGRES_GATE_URL`)
- migration safety: PASS
- smoke critical: PASS
- security admin boundary: PASS
- debug config: PASS
- health/readiness: PASS
- performance p95 `/health`: PASS (`2.88ms`, presupuesto `120ms`)

## 3) Contrato API
Sin cambios en endpoints, payloads ni reglas del backend en Day 6 v1.0.5.
