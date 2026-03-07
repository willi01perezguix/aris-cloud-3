# ARIS-CLOUD-3 (aris3) Backend/API Audit for ARIS CONTROL

> **Supuestos mínimos (por falta de OpenAPI pegado en el prompt):**
> - Se auditó la implementación actual en `app/aris3/routers/admin.py`, `app/aris3/routers/access_control.py` y repositorios `tenants/stores/users`.
> - Se asume que ARIS CONTROL consume `/aris3/admin/tenants`, `/aris3/admin/stores`, `/aris3/admin/users` y superficie ACL en `/aris3/access-control/*`.
> - Se mantienen contratos actuales como base; cualquier propuesta potencialmente disruptiva se presenta como no-breaking (additive/deprecated) o `/v2`.

## A) Diagnóstico

### Causas probables de “faltan stores/users” (ordenadas por probabilidad)

1. **Paginación por defecto con `limit=200` + UI no itera páginas completas**.
   - Hoy los listados administrativos tienen `limit` por defecto (máx 200). Si UI no pagina, habrá faltantes con datasets grandes.
   - Confirmación:
     - Revisar logs por endpoint con `limit/offset/total/count`.
     - Reproducir con `?limit=50&offset=0` y luego `offset=50`.
     - Validar que `pagination.total > pagination.count` cuando hay más datos.

2. **Scope tenant/store aplicado por rol y claims del token**.
   - Para no-superadmin, el backend fuerza tenant desde token y rechaza cross-tenant.
   - Para actores store-bound, `store_scope_id` restringe usuarios visibles.
   - Confirmación:
     - Comparar JWT claims (`role`, `tenant_id`, `store_id`) vs query enviada.
     - Revisar errores `CROSS_TENANT_ACCESS_DENIED` / `STORE_SCOPE_MISMATCH`.

3. **Filtros enviados accidentalmente desde UI (incluyendo legacy params)**.
   - `tenant_id`, `store_id`, `role`, `status`, `search` sí filtran si vienen no vacíos.
   - Existe compatibilidad legacy (`query_tenant_id`) en stores.
   - Confirmación:
     - Loggear query string raw + query normalizada.
     - Probar request con y sin cada filtro.

4. **Ordenamiento no estable en cliente (aunque backend sí agrega tie-breaker por `id`)**.
   - Backend ordena con segundo criterio por `id`; si cliente reordena localmente o mezcla páginas, puede percibirse “faltante/duplicado”.
   - Confirmación:
     - Desactivar sort local UI y validar paginación secuencial.

5. **Inconsistencia de formato de errores en endpoints legacy/admin**.
   - Coexisten `AppError` canónico y `HTTPException(detail=...)` en algunos endpoints.
   - Esto no oculta datos por sí solo, pero complica diagnóstico en UI.
   - Confirmación:
     - Forzar errores 404/409/422 y comparar shape de respuesta por endpoint.

### Cómo confirmar cada causa (queries/tests/logs)

- **Smoke paginación global superadmin**:
  - `/aris3/admin/stores?limit=50&offset=0`
  - `/aris3/admin/stores?limit=50&offset=50`
  - Verificar: `total` constante, `count<=limit`, sin overlap de IDs.

- **Scope**:
  - Superadmin sin `tenant_id` debe ver todo.
  - Tenant admin con `tenant_id` de otro tenant debe fallar explícitamente.

- **Query vacíos**:
  - Enviar `tenant_id=&search=&status=` y validar misma salida que sin esos params.

- **Errores**:
  - Generar `tenant_id` inexistente, `role` inválido, `status` inválido.
  - Confirmar contrato uniforme (o fallback legacy documentado).

### Observabilidad mínima a agregar (P0)

- Log estructurado por request de listado:
  - `trace_id`, `endpoint`, `actor_role`, `token_tenant_id`, `requested_tenant_id`, `effective_tenant_id`, `requested_store_id`, `effective_store_id`, `filters_applied`, `sort_by`, `sort_order`, `limit`, `offset`, `count`, `total`, `duration_ms`.
- Header recomendado:
  - `X-Trace-Id` espejo de `trace_id` del body.
- Métricas:
  - `admin_list_requests_total{endpoint,role}`
  - `admin_list_rows_returned{endpoint}`
  - `admin_list_total_reported{endpoint}`
  - `admin_list_cross_tenant_denied_total`

---

## B) Plan P0 / P1 / P2

### P0 (hotfix no-breaking)

1. **Enforzar normalización de query vacía en TODOS los filtros de listados** (`"" -> None`) de forma centralizada.
   - Estado: **no-breaking** (solo evita filtrado accidental).

2. **Contrato de paginación explícito en OpenAPI** para `tenants/stores/users`:
   - `pagination.total`, `pagination.count`, `pagination.limit`, `pagination.offset`, `trace_id` requeridos en response.
   - Estado: **no-breaking** (documentación + validación de respuesta existente).

3. **Observabilidad inmediata en list endpoints** (ya existe parcial; extender con `filters_applied` y tenant/store scope efectivos).
   - Estado: **no-breaking**.

4. **Parche UI-friendly opcional (`include_total=true` default true)**
   - Mantener comportamiento actual, pero documentar costo de conteo y opción futura para optimizar.
   - Estado: **no-breaking** (param aditivo).

### P1 (mejoras estructurales)

1. **Error envelope canónico transversal**:
   - `{"code","message","details","trace_id"}` en todos los errores de admin/access-control.
   - Mantener `detail` legacy temporalmente (dual-shape) para compatibilidad.
   - Estado: **no-breaking** (fallback legacy + deprecación documentada).

2. **Consistencia de ACL endpoints para UI**:
   - Publicar/estandarizar set canónico bajo `/aris3/admin/access-control/*` con mismas reglas de scope y `trace_id`.
   - Mantener endpoints hidden/legacy actuales.
   - Estado: **no-breaking** (additive + deprecación controlada).

3. **Contrato de sort robusto**:
   - Validar `sort_by` contra allowlist; tie-breaker siempre `id`.
   - Estado: **no-breaking** (ya mayormente aplicado; estandarizar).

### P2 (opcional)

1. **Cursor pagination dual-mode** (`page_token`) en paralelo a `limit/offset`.
   - `mode=offset|cursor` o auto por presencia de token.
   - Estado: **no-breaking** si offset/limit se mantiene intacto.

2. **Snapshots consistentes para listados críticos** (si hay alta concurrencia).
   - Cursor basado en `(sort_field,id)` para evitar drift.
   - Estado: **no-breaking** (nuevo modo).

3. **Cache corto para permission catalog / role templates**.
   - Estado: **no-breaking**.

---

## C) Cambios concretos al OpenAPI (snippets/diffs)

### C.1. Parámetros estándar de listados

```yaml
components:
  parameters:
    LimitParam:
      name: limit
      in: query
      schema: { type: integer, minimum: 1, maximum: 200, default: 200 }
      description: Tamaño de página (máx 200).
    OffsetParam:
      name: offset
      in: query
      schema: { type: integer, minimum: 0, default: 0 }
      description: Offset de paginación.
    SortOrderParam:
      name: sort_order
      in: query
      schema: { type: string, enum: [asc, desc], default: asc }
```

### C.2. Response envelope de listados

```yaml
components:
  schemas:
    PaginationMeta:
      type: object
      required: [total, count, limit, offset]
      properties:
        total: { type: integer, minimum: 0 }
        count: { type: integer, minimum: 0 }
        limit: { type: integer, minimum: 1 }
        offset: { type: integer, minimum: 0 }

    StoreListResponse:
      type: object
      required: [stores, pagination, trace_id]
      properties:
        stores:
          type: array
          items: { $ref: '#/components/schemas/StoreItem' }
        pagination: { $ref: '#/components/schemas/PaginationMeta' }
        trace_id: { type: string }
```

### C.3. Error canónico (dual-shape compatible)

```yaml
components:
  schemas:
    ApiError:
      type: object
      required: [code, message, trace_id]
      properties:
        code: { type: string }
        message: { type: string }
        details: { nullable: true }
        trace_id: { type: string }
        detail:
          description: Campo legacy mantenido temporalmente por compatibilidad.
          nullable: true
```

### C.4. ACL efectivos determinísticos

```yaml
paths:
  /aris3/access-control/effective-permissions:
    get:
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                required: [subject, permissions, denies_applied, sources_trace, trace_id]
```

---

## D) Implementación FastAPI (pseudocódigo + SQL/ORM)

### D.1. Reglas de scope (tenants/stores/users)

```python
def normalize_optional(v: str | None) -> str | None:
    if v is None:
        return None
    value = v.strip()
    return value or None

requested_tenant_id = normalize_optional(query.tenant_id)
if is_superadmin(token.role):
    effective_tenant_id = requested_tenant_id  # None => GLOBAL
else:
    effective_tenant_id = token.tenant_id
    if requested_tenant_id and requested_tenant_id != token.tenant_id:
        raise AppError(CROSS_TENANT_ACCESS_DENIED)
```

### D.2. Filtros solo si vienen

```python
if status is not None:  # ya normalizado
    stmt = stmt.where(func.lower(Model.status) == status.lower())
# si status None => NO filtro implícito ACTIVE
```

### D.3. Orden estable + total correcto

```python
sort_column = {
    "name": Store.name,
    "created_at": Store.created_at,
}.get(sort_by, Store.name)

stmt = stmt.order_by(
    sort_column.asc() if sort_order == "asc" else sort_column.desc(),
    Store.id.asc() if sort_order == "asc" else Store.id.desc(),
)

rows_stmt = stmt.limit(limit).offset(offset)
rows = db.execute(rows_stmt).scalars().all()
total = db.execute(count_stmt).scalar_one()
```

### D.4. Effective permissions determinístico

Orden recomendado de resolución (última regla prevalece en deny explícito):
1. Role template allow
2. Tenant overlay allow/deny
3. Store overlay allow/deny
4. User override allow/deny
5. `denies_applied` = conjunto final de denies activos

```python
trace = {
  "template": {"allow": [...]},
  "tenant": {"allow": [...], "deny": [...]},
  "store": {"allow": [...], "deny": [...]},
  "user": {"allow": [...], "deny": [...]},
}
```

---

## E) Checklist de pruebas

### Manuales (Swagger/curl)

1. Superadmin sin tenant_id:
   - `GET /aris3/admin/tenants`
   - `GET /aris3/admin/stores`
   - `GET /aris3/admin/users`
   - Esperado: visión global.

2. Query vacías:
   - `GET /aris3/admin/users?tenant_id=&store_id=&search=&status=`
   - Esperado: igual que sin filtros.

3. Paginación >200:
   - poblar >200 stores/users.
   - iterar offsets 0/50/100...
   - validar suma sin faltantes.

4. Formato de error único:
   - role inválido, status inválido, cross-tenant.
   - validar `code/message/details/trace_id`.

### Automáticas (pytest)

- `test_admin_users_superadmin_global_scope_lists_all()`
- `test_admin_stores_pagination_stable_over_200_records()`
- `test_admin_users_empty_query_params_do_not_filter()`
- `test_admin_users_status_not_sent_does_not_filter_active_only()`
- `test_admin_list_trace_id_always_present()`
- `test_access_control_effective_permissions_deterministic_trace()`
- `test_error_envelope_canonical_with_legacy_detail_fallback()`

---

## F) Lista “NO TOCAR / NO ROMPER”

1. **Rutas existentes `/aris3/...`** deben mantenerse operativas (ARIS OPERADOR).
2. **Campos existentes** de responses actuales no se renombrarán ni eliminarán.
3. **Parámetros existentes** no se eliminan; si sobran => `deprecated` + soporte temporal.
4. **Semántica actual** solo evoluciona en modo compatible:
   - Additive fields/endpoints, o
   - `/v2` / feature flag para cambios mayores.

### Plan de transición para deprecaciones

- **Fase 1 (ahora)**: mantener legacy + documentar canónico.
- **Fase 2**: emitir warning header (`Deprecation`, `Sunset`) en rutas legacy.
- **Fase 3**: migrar UI/SDK a canónico; remover solo en versión mayor.

---

## Bonus: índices y performance recomendados

- `stores(tenant_id, name, id)` para list/sort por name.
- `stores(tenant_id, created_at, id)` para sort por created_at.
- `users(tenant_id, store_id, role, status, is_active, id)` (ajustar orden según selectividad real).
- Índices funcionales para búsquedas case-insensitive:
  - `LOWER(users.username)`, `LOWER(users.email)`, `LOWER(tenants.name)`, `LOWER(stores.name)`.
- `permission_catalog` cache in-memory/redis con TTL corto (30–120s) si hay alta frecuencia.

