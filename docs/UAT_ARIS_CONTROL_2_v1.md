# UAT ARIS_CONTROL_2 v1 (Prompt 8)

## Alcance validado
- Login (`username_or_email`/`password`) + `/me` + armado de `SessionContext`.
- Tenant selector para `SUPERADMIN` y enforcement tenant-scoped.
- Stores y Users list/create con `effective_tenant_id`.
- User actions (`set_status`, `set_role`, `reset_password`) con guardrails RBAC.
- Error handling visible con `code`/`message`/`trace_id`.
- Idempotencia de mutaciones en create/actions.
- Retry/timeout para transitorios y no-retry en 4xx.

## Evidencia automatizada ejecutada
- `pytest ARIS_CONTROL_2/tests/unit ARIS_CONTROL_2/tests/integration -q`
- Resultado: `23 passed`.

## Casos críticos U1..U6
| Caso | Evidencia | Resultado |
|---|---|---|
| U1 SUPERADMIN sin `selected_tenant_id` bloqueado en Stores/Users | `test_u1_superadmin_without_selected_tenant_blocked_from_stores_users` | PASS |
| U2 SUPERADMIN selecciona tenant A y opera scope A | `test_tenant_switch_resets_dependent_state` + política efectiva en `TenantContextPolicy` | PASS |
| U3 ADMIN/MANAGER usan `token_tenant_id` (sin inyección UI) | `test_stores_use_effective_tenant_and_idempotency` y `test_users_use_effective_tenant_and_actions_refresh` | PASS |
| U4 create user con store cruzada devuelve `TENANT_STORE_MISMATCH` + trace | `test_u4_cross_tenant_store_in_user_create_surfaces_trace_id` | PASS |
| U5 acción no permitida devuelve `PERMISSION_DENIED` + trace | `test_u5_permission_denied_action_visible_with_trace_id` | PASS |
| U6 replay idempotente no duplica y devuelve estado semántico | `test_u6_idempotent_replay_does_not_duplicate_create_or_action` | PASS |

## Matriz de permisos efectivos (UI vs backend)
- UI (`PermissionGate`) usa `effective_permissions` y falla cerrado (default deny).
- Casos validados:
  - Acción oculta si falta permiso (`users.actions`).
  - SUPERADMIN requiere tenant seleccionado para recursos tenant-scoped.
- Backend/SDK sigue autoridad final: errores API (`PERMISSION_DENIED`, `TENANT_STORE_MISMATCH`) suben al mapper con `trace_id`.
- Discrepancias detectadas: ninguna funcional en esta corrida.

## Estabilidad / resiliencia cliente
- Retry en timeout/5xx validado (`test_retry_on_5xx_and_timeout`).
- No retry en 4xx funcional validado (`test_no_retry_on_4xx`).
- Doble submit cubierto vía idempotency-key + replay semantic status en use cases.

## Observabilidad / trazabilidad
- Contrato de log cliente validado (`ts`, `level`, `module`, `action`, `actor_role`, `effective_tenant_id`, `trace_id`, `outcome`).
- Validación explícita de ausencia de secretos (`password`, `access_token`) en logs.
- Correlación `trace_id` visible en mensajes de error (`ErrorMapper` / `ErrorBanner`).

## Evidencia Packaging Windows (RC inicial)
- Scripts presentes: `scripts/windows/build_control_center.ps1`, `scripts/windows/run_control_center_dev.ps1`.
- Template presente: `packaging/control_center.spec.template`.
- Limitación de entorno CI actual:
  - `pwsh` no está instalado.
  - `pip install pyinstaller` bloqueado por red/proxy.
- Resultado packaging/smoke en este entorno: **no ejecutable** (pendiente en runner Windows).
