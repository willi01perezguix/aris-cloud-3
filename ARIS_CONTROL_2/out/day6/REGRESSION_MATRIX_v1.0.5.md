# Matriz de regresión v1.0.4 -> v1.0.5 (Day 6)

## Estado general
- Esperado: no romper flujo base, RBAC visual, trazabilidad y exportes.
- Resultado: **sin regresiones críticas detectadas**.

| Área | Esperado | Evidencia | Resultado |
|---|---|---|---|
| Flujo base Tenant/Store/User | Operativo sin ruptura | `tests/integration/test_stores_tenant_scope.py`, `tests/integration/test_users_tenant_scope_and_actions.py` | PASS |
| RBAC visual por rol | Guardas UI y acciones sensibles correctas | `tests/integration/test_users_actions_rbac_ui_guard.py` | PASS |
| Trazabilidad code/message/trace_id | Errores observables y trazables | `tests/unit/test_day5_diagnostics_and_context.py`, `scripts/release_readiness_gate.py` logs `trace_id` | PASS |
| Export de vista + soporte | Export y paquete soporte disponibles | `tests/unit/test_day5_support_package.py` | PASS |
| Login/sesión y 401/403 | Sesión y rechazos controlados | `tests/unit/test_auth_me_clients.py`, `tests/integration/test_login_me_context.py` | PASS |
| Idempotencia UI anti doble submit | Reintentos/mutaciones protegidas | `tests/integration/test_uat_guardrails_and_idempotency.py` | PASS |
| Filtros/paginación/estado | Persistencia y reset controlado | `tests/unit/test_pagination_ui_state.py`, `tests/unit/test_day2_listing_state_and_debounce.py` | PASS |

## Hallazgos

### Esperados
1. `tests:postgres` queda en WARN en gate si no se define `POSTGRES_GATE_URL`.
2. Build `.exe` requiere runner Windows con PowerShell (`pwsh`) y cadena de build oficial.

### No esperados (no críticos)
1. `tests/unit/test_day1_kickoff_quickwins.py::test_tenant_change_clears_incompatible_users_store_filter` falla por discrepancia de limpieza de filtros (`{}` vs `{"q":"alice"}`).
   - Riesgo: bajo.
   - Alcance: UX local de filtros, sin impacto de contrato API.
