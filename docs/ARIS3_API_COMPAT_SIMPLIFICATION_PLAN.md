# ARIS-CLOUD-3 · Plan de simplificación API/OpenAPI sin breaking

Este documento propone cómo simplificar la superficie de API y OpenAPI **sin romper** ARIS OPERADOR ni ARIS CONTROL.

## A) Inventario de endpoints y decisión

| Endpoint | Quién lo usa | Decisión | Notas de compatibilidad |
|---|---|---|---|
| `GET/POST /aris3/admin/tenants` | CONTROL | KEEP | CRUD core de administración. Mantener paginación `limit/offset` y defaults. |
| `GET/PATCH/DELETE /aris3/admin/tenants/{tenant_id}` | CONTROL | KEEP | Mantener contrato; status canónico en mayúsculas aceptando minúsculas legacy. |
| `POST /aris3/admin/tenants/{tenant_id}/actions` | CONTROL | KEEP | Mantener para acciones administrativas (ej. `set_status`). |
| `GET/POST /aris3/admin/stores` | CONTROL | KEEP | Mantener `query_tenant_id` como **legacy deprecated** y `tenant_id` body como canónico. |
| `GET/PATCH/DELETE /aris3/admin/stores/{store_id}` | CONTROL | KEEP | CRUD core de administración. |
| `GET/POST /aris3/admin/users` | CONTROL | KEEP | Mantener `tenant_id` body solo por compatibilidad (derivado desde `store_id`). |
| `GET/PATCH/DELETE /aris3/admin/users/{user_id}` | CONTROL | KEEP | CRUD core de usuarios. |
| `POST /aris3/admin/users/{user_id}/actions` | CONTROL | KEEP | Mantener acciones (`set_status`, `set_role`, `reset_password`) por estabilidad operativa. |
| `GET /aris3/admin/access-control/permission-catalog` | CONTROL | KEEP | Catálogo admin para UI de permisos/roles. |
| `GET/PUT /aris3/admin/access-control/role-templates/{role_name}` | CONTROL | KEEP | Gestión base RBAC; no romper. |
| `GET/PUT /aris3/admin/access-control/tenants/{tenant_id}/role-policies/{role_name}` | CONTROL | KEEP | Overlays por tenant. |
| `GET/PUT /aris3/admin/access-control/stores/{store_id}/role-policies/{role_name}` | CONTROL | KEEP | Overlays por store. |
| `GET/PATCH /aris3/admin/access-control/user-overrides/{user_id}` | CONTROL | KEEP | Overrides por usuario; clave para soporte fino. |
| `GET /aris3/admin/access-control/effective-permissions` | CONTROL | KEEP | Endpoint diagnóstico/validación de permisos. Agregar `include_sources_trace` opcional para simplificar payload por defecto. |
| `GET/PATCH /aris3/admin/settings/return-policy` | CONTROL | KEEP | Configuración administrativa vigente. |
| `GET/PATCH /aris3/admin/settings/variant-fields` | CONTROL | KEEP | Configuración administrativa vigente. |
| `GET /aris3/access-control/effective-permissions` | OPERADOR + CONTROL | KEEP | Endpoint self crítico para autorización contextual. |
| `GET /aris3/access-control/permission-catalog` | OPERADOR + CONTROL | KEEP | Catálogo self útil para cliente/feature flags. |
| `POST /aris3/auth/login` | OPERADOR + CONTROL | KEEP | Login JSON principal. **No tocar**. |
| `POST /aris3/auth/token` | SWAGGER (+ integraciones OAuth2) | HIDE-IN-DOCS | Mantener funcional por compatibilidad, pero etiquetar `Swagger Only` y documentar que `login` es canónico. |
| `POST /aris3/auth/change-password` | OPERADOR + CONTROL | KEEP | Método canónico recomendado. |
| `PATCH /aris3/auth/change-password` | OPERADOR + CONTROL (legacy) | DEPRECATE | Mantener como alias al mismo handler, marcar `deprecated=true`. |
| `GET /aris3/me` | OPERADOR + CONTROL | KEEP | Endpoint self crítico. **No tocar**. |
| `GET /health` | OPERADOR/OPS | KEEP | Salud liveness. |
| `GET /ready` | OPERADOR/OPS | KEEP | Salud readiness. |
| Rutas ACL legacy ocultas con `include_in_schema=False` | Legacy interno | REMOVE-LATER | Mantener funcionando, no exponer en OpenAPI. Plan de retiro en P2 con métricas de uso previas. |

## B) Plan P0 / P1 / P2

### P0 (inmediato, no breaking)
1. Marcar como `deprecated` todo lo legacy que debe seguir funcionando (ej. `PATCH /auth/change-password`, `query_tenant_id`).
2. Separar tags OpenAPI: `Admin`, `Self`, `Swagger Only` para lectura nítida del contrato.
3. Establecer en docs y schema reglas canónicas:
   - paginación uniforme (`limit<=200`, `limit=200`, `offset=0`),
   - status canónico en mayúsculas, aceptando minúsculas,
   - campos legacy explícitos como deprecated.
4. En `effective-permissions`, agregar query opcional `include_sources_trace` default `false` para reducir ruido sin romper (si `true`, devolver trazas completas).
5. Mantener envelope de errores estable (`code/message/details/trace_id`) y mapear variantes existentes sin romper clientes actuales.

### P1 (cambios menores compatibles)
1. Añadir headers de deprecación (`Deprecation`, `Sunset`) en alias legacy.
2. Instrumentar métricas de uso por endpoint/param legacy (ej. uso de `PATCH change-password`, `query_tenant_id`, `/auth/token`).
3. Normalizar documentación de respuestas de error por endpoint para reflejar un único envelope canónico (manteniendo adaptadores para formatos previos).
4. Endurecer validaciones de paginación y status en un módulo compartido para evitar drift entre routers.

### P2 (limpieza mayor con migración explícita)
1. Retirar de docs y luego desactivar rutas legacy ocultas solo cuando la telemetría confirme 0 uso o uso controlado.
2. Evaluar retiro de `PATCH /auth/change-password` y/o `/auth/token` como públicos tras ventana de migración comunicada.
3. Consolidar completamente el envelope de errores si hoy aún conviven formatos distintos, con versión de contrato/migration guide.

## C) Snippets OpenAPI (YAML)

### 1) Marcar endpoint y parámetro como deprecated

```yaml
paths:
  /aris3/auth/change-password:
    patch:
      tags: [Self]
      summary: Change password (legacy alias)
      deprecated: true
      responses:
        '200':
          description: OK

  /aris3/admin/stores:
    post:
      tags: [Admin Stores]
      parameters:
        - in: query
          name: query_tenant_id
          schema: { type: string }
          required: false
          deprecated: true
          description: "Legacy. Use tenant_id in JSON body."
```

### 2) Tags separados (Admin vs Self vs Swagger Only)

```yaml
tags:
  - name: Admin Tenants
    description: Tenant lifecycle administration.
  - name: Admin Stores
    description: Store lifecycle administration.
  - name: Admin Users
    description: User lifecycle administration.
  - name: Admin Access Control
    description: ACL management surface.
  - name: Admin Settings
    description: Runtime tenant settings.
  - name: Access Control (Self)
    description: Self-context read endpoints.
  - name: Swagger Only
    description: Endpoints kept mainly for Swagger/OAuth tooling compatibility.

paths:
  /aris3/auth/token:
    post:
      tags: [Swagger Only]
      summary: OAuth2 token helper for Swagger
```

### 3) `include_sources_trace` opcional en effective-permissions

```yaml
paths:
  /aris3/admin/access-control/effective-permissions:
    get:
      parameters:
        - in: query
          name: include_sources_trace
          required: false
          schema:
            type: boolean
            default: false
          description: "If true, include sources_trace for ACL diagnostics."
      responses:
        '200':
          description: Effective permissions
```

## D) Notas de implementación FastAPI (pseudocódigo)

### 1) Alias POST/PATCH `change-password` sin duplicar lógica

```python
@router.post("/change-password", response_model=ChangePasswordResponse)
@router.patch("/change-password", response_model=ChangePasswordResponse, deprecated=True)
async def change_password(request: Request, payload: ChangePasswordRequest, ...):
    return await _change_password_impl(request, payload, ...)

async def _change_password_impl(request, payload, ...):
    # idempotency + audit + service.change_password
    ...
```

### 2) `query_tenant_id` legacy en create store

```python
@router.post("/aris3/admin/stores")
async def create_store(payload: StoreCreateRequest, query_tenant_id: str | None = Query(None, deprecated=True), ...):
    canonical_tenant_id = payload.tenant_id
    legacy_tenant_id = query_tenant_id

    if canonical_tenant_id and legacy_tenant_id and canonical_tenant_id != legacy_tenant_id:
        raise validation_error("tenant_id and query_tenant_id must match")

    resolved_tenant_id = canonical_tenant_id or legacy_tenant_id
    # aplicar reglas de scope/rol sin fallback implícito para superadmin
    ...
```

### 3) Unificar error envelope + `trace_id`

```python
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.error.code,
            "message": exc.error.message,
            "details": exc.details,
            "trace_id": trace_id,
        },
    )

@app.middleware("http")
async def trace_middleware(request, call_next):
    request.state.trace_id = request.headers.get("X-Trace-Id") or generate_trace_id()
    return await call_next(request)
```

## E) Checklist de pruebas

### Manual (Swagger / curl)
1. Verificar que endpoints deprecated siguen respondiendo 200/4xx esperados:
   - `PATCH /aris3/auth/change-password`
   - `POST /aris3/admin/stores?query_tenant_id=...`
2. Verificar paginación canonical en listados:
   - default `limit=200, offset=0`
   - rechazo o clamp para `limit>200`.
3. Verificar status:
   - aceptar `ACTIVE/SUSPENDED/CANCELED`
   - aceptar `active/suspended/canceled` por compatibilidad.
4. Verificar ACL effective-permissions con y sin `include_sources_trace=true`.
5. Verificar envelope de error uniforme con `trace_id` presente.

### Unit tests (pytest)
1. `test_auth_change_password_post_and_patch_share_same_behavior`.
2. `test_create_store_accepts_body_tenant_id_or_legacy_query_tenant_id`.
3. `test_create_store_rejects_mismatched_tenant_sources`.
4. `test_list_endpoints_pagination_defaults_and_limit_cap_200`.
5. `test_status_accepts_upper_and_lower_case_variants`.
6. `test_effective_permissions_include_sources_trace_flag`.
7. `test_error_envelope_contains_code_message_details_trace_id`.
8. `test_operator_critical_endpoints_not_deprecated` (`/auth/login`, `/me`, `/access-control/effective-permissions`).

## F) Lista explícita NO TOCAR / NO ROMPER (ARIS OPERADOR)

1. `POST /aris3/auth/login` (flujo principal de autenticación).
2. `GET /aris3/me` (identidad/autorización del usuario autenticado).
3. `GET /aris3/access-control/effective-permissions` (resolución ACL runtime del operador).
4. `GET /aris3/access-control/permission-catalog` (catálogo runtime consumible por cliente).
5. Contrato de errores consumido por operador (`code/message/details/trace_id` o compatibilidad equivalente vigente).
6. Reglas actuales de scopes del JWT (tenant/store/user) que afectan autorización en runtime.
7. Cualquier ruta de salud usada por despliegue/monitoreo (`/health`, `/ready`).
