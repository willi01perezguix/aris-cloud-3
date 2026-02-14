# Matriz de regresión v1.0.3 -> v1.0.4

Fecha: 2026-02-14

| Área de no-regresión requerida | Validación ejecutada | Estado | Tipo |
|---|---|---|---|
| Flujo base Tenant/Store/User | Integration tests de login/contexto/stores/users + backend `test_tenant_store_user_integrity.py` | PASS | Esperado |
| RBAC visual (acciones permitidas/no permitidas) | `tests/integration/test_users_actions_rbac_ui_guard.py`, `tests/unit/test_tenants_view_rbac_visibility.py` | PASS | Esperado |
| Idempotencia UI anti-doble-submit | `tests/unit/test_mutation_attempts.py`, `tests/unit/test_idempotency_key_factory.py`, backend `tests/test_idempotency_admin.py` | PASS | Esperado |
| Persistencia tenant/filtros/paginación | `tests/unit/test_pagination_ui_state.py`, `tests/integration/test_tenant_switch_state_reset.py`, `tests/unit/test_day5_listing_cache_and_refresh.py` | PASS | Esperado |
| Export CSV de vista filtrada | `tests/unit/test_csv_exporter.py`, backend `tests/test_exports_day4_download.py` | PASS | Esperado |

## Mejoras esperadas observadas
- Sin cambios de contrato API ni regresiones en cobertura crítica.
- El baseline de pruebas mantiene trazabilidad de errores estructurados (`code/message/trace_id`) y guardrails de mutaciones admin.

## Hallazgos no esperados
- **Ninguno en pruebas automáticas**.

## Bloqueos externos (no regresión de código)
- Ejecución de smoke E2E manual y build Windows RC limitada por entorno CI Linux sin PowerShell/runner Windows.
