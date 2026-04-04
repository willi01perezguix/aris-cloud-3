# API Prune Report (agresivo) — ARIS-CLOUD-3

## Alcance y evidencia real usada
- En este repo **no están presentes** los árboles fuente de `ARIS Control` ni `ARIS Operador` como proyectos separados; se usó como evidencia ejecutable el consumo en pruebas backend e2e/integración del propio monorepo.
- Evidencia principal usada para podas realizadas:
  - `tests/test_admin_auth_contract_hardening.py` (uso de `/aris3/auth/change-password`, `/aris3/admin/stores`, `/aris3/admin/users`).
  - `tests/test_pos_sales_day6_stock_deduction.py` y `tests/test_reports_day3_overview.py` (uso de `/aris3/pos/sales` y `/aris3/pos/sales/{sale_id}/actions`).

## Matriz resumida KEEP / DELETE / KEEP_CANONICAL_ONLY

| Endpoint / contrato | Control | Operador | Evidencia | Decisión |
|---|---:|---:|---|---|
| `PATCH /aris3/auth/change-password` | Sí | Sí | tests admin/auth | KEEP |
| `POST /aris3/auth/change-password` | No canónico | No canónico | alias legacy en router auth | DELETE |
| `GET /aris3/admin/stores?query_tenant_id=...` | Legacy | N/A | tests admin legacy query | DELETE |
| `POST /aris3/admin/stores` con `query_tenant_id` | Legacy | N/A | router admin tenía compat | DELETE |
| `GET /aris3/admin/users?is_active=...` | Legacy | N/A | tests admin legacy filter | DELETE |
| `GET /aris3/pos/sales?from_date=&to_date=` | Legacy | Sí (listado ventas) | router pos_sales | DELETE (dejar canónico) |
| `GET /aris3/pos/sales?checked_out_from=&checked_out_to=` | Sí | Sí | tests pos sales | KEEP |
| `POST /aris3/pos/sales/{sale_id}/actions` `action=REFUND_ITEMS` | Legacy | Legacy | flujo legacy coexistente | KEEP_CANONICAL_ONLY (schema) |
| `POST /aris3/pos/sales/{sale_id}/actions` `action=EXCHANGE_ITEMS` | Legacy | Legacy | flujo legacy coexistente | KEEP_CANONICAL_ONLY (schema) |
| `POST /aris3/pos/sales/{sale_id}/actions` `action=CHECKOUT|CANCEL` | Sí | Sí | tests pos sales | KEEP |

## Podas aplicadas en código

### Endpoints / aliases removidos
- Eliminado alias `POST /aris3/auth/change-password`; se deja únicamente `PATCH`.

### Params removidos
- Eliminado `query_tenant_id` de `GET /aris3/admin/stores`.
- Eliminado `query_tenant_id` (y fallback implícitos) de `POST /aris3/admin/stores`.
- Eliminado filtro `is_active` de `GET /aris3/admin/users`.
- Eliminados `from_date` / `to_date` de `GET /aris3/pos/sales`; quedan `checked_out_from` / `checked_out_to`.
- Eliminado `tenant_id` legacy en requests de creación/edición/acciones de POS sales.

### Compatibilidad legacy removida en schemas
- `AdminUserStatus` ya no acepta lowercase (`active/suspended/canceled`), solo canonical uppercase.
- `PosSaleActionRequest` mantiene el union completo canónico (`CHECKOUT`, `CANCEL`, `REFUND_ITEMS`, `EXCHANGE_ITEMS`) para evitar drift entre runtime y Swagger.

## OpenAPI final (canónico)
- Fuente de verdad: runtime OpenAPI exportado en `artifacts/release_candidate/openapi.json`.
- `docs/openapi-pruned.json` se retiró por ser no canónico y propenso a drift.

## Breaking changes reales
1. Clientes que usen `POST /aris3/auth/change-password` deben migrar a `PATCH`.
2. Clientes que usen `query_tenant_id` en stores deben migrar a `tenant_id` canónico.
3. Clientes que filtren users por `is_active` deben migrar a `status` (`ACTIVE|SUSPENDED|CANCELED`).
4. Clientes que usen `from_date/to_date` en ventas deben migrar a `checked_out_from/checked_out_to`.
5. Clientes que envíen `tenant_id` en payloads de POS sales deben dejar de enviarlo.
6. Swagger/clientes generados deben consumir el discriminador completo de acciones POS (`CHECKOUT`, `CANCEL`, `REFUND_ITEMS`, `EXCHANGE_ITEMS`).

## Módulos completos eliminados
- Ninguno en esta iteración (poda enfocada en contratos/aliases legacy de auth/admin/pos sales).
