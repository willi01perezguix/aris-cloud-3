# Auditoría API ARIS-CLOUD-3 (FastAPI + Postgres)

## Supuestos de compatibilidad usados en esta auditoría
1. **No se tocan rutas existentes** bajo `/aris3/*`.
2. **Paginación canónica**: `limit/offset`, con `limit <= 200`.
3. **Estados canónicos en mayúscula** (`ACTIVE`, `SUSPENDED`, `CANCELED`), aceptando minúsculas en input por compatibilidad.
4. **Envelope consistente** con `trace_id`.
5. **No romper ARIS OPERADOR** (prioridad en POS, stock, transfers, cash, returns, sales).

## A) Inventario de endpoints por tags + clasificación

> Leyenda clasificación:
> - **KEEP**: mantener como estable.
> - **HIDE-IN-DOCS**: mantener operativo pero no exponer en OpenAPI pública.
> - **DEPRECATE**: mantener temporalmente con sunset y alternativa explícita.
> - **REMOVE**: retirar solo en ventana breaking (P2) y con evidencia de no uso.

### auth
| Método | Endpoint | Clasificación | Probable uso |
|---|---|---|---|
| POST | `/aris3/auth/login` | KEEP | ARIS CONTROL + ARIS OPERADOR |
| POST | `/aris3/auth/token` | KEEP | Infra/Dev (integraciones, scripts) |
| POST | `/aris3/auth/change-password` | KEEP | ARIS CONTROL + ARIS OPERADOR |
| PATCH | `/aris3/auth/change-password` | DEPRECATE | Compat legacy (clientes antiguos) |

### users
| Método | Endpoint | Clasificación | Probable uso |
|---|---|---|---|
| GET | `/aris3/me` | KEEP | ARIS CONTROL + ARIS OPERADOR |

### access-control (self/legacy)
| Método | Endpoint | Clasificación | Probable uso |
|---|---|---|---|
| GET | `/aris3/access-control/effective-permissions` | KEEP | ARIS CONTROL |
| GET | `/aris3/access-control/permission-catalog` | KEEP | ARIS CONTROL |
| GET | `/aris3/access-control/effective-permissions/users/{user_id}` | HIDE-IN-DOCS | Infra/Dev + legacy admin |
| GET | `/aris3/access-control/tenants/{tenant_id}/stores/{store_id}/users/{user_id}/effective-permissions` | HIDE-IN-DOCS | Infra/Dev + legacy admin |
| GET | `/aris3/access-control/tenants/{tenant_id}/role-policies/{role_name}` | HIDE-IN-DOCS | Infra/Dev |
| PUT | `/aris3/access-control/tenants/{tenant_id}/role-policies/{role_name}` | HIDE-IN-DOCS | Infra/Dev |
| GET | `/aris3/access-control/tenants/{tenant_id}/stores/{store_id}/role-policies/{role_name}` | HIDE-IN-DOCS | Infra/Dev |
| PUT | `/aris3/access-control/tenants/{tenant_id}/stores/{store_id}/role-policies/{role_name}` | HIDE-IN-DOCS | Infra/Dev |
| GET | `/aris3/access-control/tenants/{tenant_id}/users/{user_id}/permission-overrides` | HIDE-IN-DOCS | Infra/Dev |
| PUT | `/aris3/access-control/tenants/{tenant_id}/users/{user_id}/permission-overrides` | HIDE-IN-DOCS | Infra/Dev |
| GET | `/aris3/access-control/platform/role-policies/{role_name}` | HIDE-IN-DOCS | Infra/Dev |
| PUT | `/aris3/access-control/platform/role-policies/{role_name}` | HIDE-IN-DOCS | Infra/Dev |

### admin (tenants/stores/users/access-control/settings)
| Método | Endpoint | Clasificación | Probable uso |
|---|---|---|---|
| GET | `/aris3/admin/access-control/permission-catalog` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/access-control/role-templates/{role_name}` | KEEP | ARIS CONTROL |
| PUT | `/aris3/admin/access-control/role-templates/{role_name}` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/settings/return-policy` | KEEP | ARIS CONTROL |
| PATCH | `/aris3/admin/settings/return-policy` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/access-control/tenant-role-policies/{role_name}` | KEEP | ARIS CONTROL |
| PUT | `/aris3/admin/access-control/tenant-role-policies/{role_name}` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/access-control/store-role-policies/{store_id}/{role_name}` | KEEP | ARIS CONTROL |
| PUT | `/aris3/admin/access-control/store-role-policies/{store_id}/{role_name}` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/access-control/user-overrides/{user_id}` | KEEP | ARIS CONTROL |
| PATCH | `/aris3/admin/access-control/user-overrides/{user_id}` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/access-control/effective-permissions` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/tenants` | KEEP | ARIS CONTROL |
| POST | `/aris3/admin/tenants` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/tenants/{tenant_id}` | KEEP | ARIS CONTROL |
| PATCH | `/aris3/admin/tenants/{tenant_id}` | KEEP | ARIS CONTROL |
| DELETE | `/aris3/admin/tenants/{tenant_id}` | KEEP | ARIS CONTROL |
| POST | `/aris3/admin/tenants/{tenant_id}/actions` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/stores` | KEEP | ARIS CONTROL |
| POST | `/aris3/admin/stores` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/stores/{store_id}` | KEEP | ARIS CONTROL |
| PATCH | `/aris3/admin/stores/{store_id}` | KEEP | ARIS CONTROL |
| DELETE | `/aris3/admin/stores/{store_id}` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/users` | KEEP | ARIS CONTROL |
| POST | `/aris3/admin/users` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/users/{user_id}` | KEEP | ARIS CONTROL |
| PATCH | `/aris3/admin/users/{user_id}` | KEEP | ARIS CONTROL |
| DELETE | `/aris3/admin/users/{user_id}` | KEEP | ARIS CONTROL |
| POST | `/aris3/admin/users/{user_id}/actions` | KEEP | ARIS CONTROL |
| GET | `/aris3/admin/settings/variant-fields` | KEEP | ARIS CONTROL |
| PATCH | `/aris3/admin/settings/variant-fields` | KEEP | ARIS CONTROL |

### stock
| Método | Endpoint | Clasificación | Probable uso |
|---|---|---|---|
| GET | `/aris3/stock` | KEEP | ARIS OPERADOR + ARIS CONTROL |
| POST | `/aris3/stock/import-epc` | KEEP | ARIS CONTROL (backoffice) |
| POST | `/aris3/stock/import-sku` | DEPRECATE | Compat legacy; migrar a EPC |
| POST | `/aris3/stock/migrate-sku-to-epc` | KEEP | Infra/Dev + migración controlada |
| POST | `/aris3/stock/actions` | KEEP | ARIS OPERADOR |

### transfers
| Método | Endpoint | Clasificación | Probable uso |
|---|---|---|---|
| GET | `/aris3/transfers` | KEEP | ARIS OPERADOR + ARIS CONTROL |
| GET | `/aris3/stores` | KEEP | ARIS OPERADOR (selector origen/destino) |
| POST | `/aris3/transfers` | KEEP | ARIS OPERADOR |
| PATCH | `/aris3/transfers/{transfer_id}` | KEEP | ARIS OPERADOR |
| GET | `/aris3/transfers/{transfer_id}` | KEEP | ARIS OPERADOR + ARIS CONTROL |
| POST | `/aris3/transfers/{transfer_id}/actions` | KEEP | ARIS OPERADOR |

### pos-sales
| Método | Endpoint | Clasificación | Probable uso |
|---|---|---|---|
| GET | `/aris3/pos/sales` | KEEP | ARIS OPERADOR |
| POST | `/aris3/pos/sales` | KEEP | ARIS OPERADOR |
| PATCH | `/aris3/pos/sales/{sale_id}` | KEEP | ARIS OPERADOR |
| GET | `/aris3/pos/sales/{sale_id}` | KEEP | ARIS OPERADOR |
| POST | `/aris3/pos/sales/{sale_id}/actions` | KEEP | ARIS OPERADOR |

### pos-returns
| Método | Endpoint | Clasificación | Probable uso |
|---|---|---|---|
| GET | `/aris3/pos/returns` | KEEP | ARIS OPERADOR |
| GET | `/aris3/pos/returns/{return_id}` | KEEP | ARIS OPERADOR |
| GET | `/aris3/pos/returns/eligibility` | KEEP | ARIS OPERADOR |
| POST | `/aris3/pos/returns/quote` | KEEP | ARIS OPERADOR |
| POST | `/aris3/pos/returns` | KEEP | ARIS OPERADOR |
| POST | `/aris3/pos/returns/{return_id}/actions` | KEEP | ARIS OPERADOR |

### pos-cash
| Método | Endpoint | Clasificación | Probable uso |
|---|---|---|---|
| GET | `/aris3/pos/cash/session/current` | KEEP | ARIS OPERADOR |
| POST | `/aris3/pos/cash/session/actions` | KEEP | ARIS OPERADOR |
| GET | `/aris3/pos/cash/movements` | KEEP | ARIS OPERADOR + ARIS CONTROL |
| POST | `/aris3/pos/cash/day-close/actions` | KEEP | ARIS OPERADOR |
| GET | `/aris3/pos/cash/day-close/summary` | KEEP | ARIS CONTROL |
| GET | `/aris3/pos/cash/reconciliation/breakdown` | KEEP | ARIS CONTROL |

### reports / exports / assets / ops / health
| Método | Endpoint | Clasificación | Probable uso |
|---|---|---|---|
| GET | `/aris3/reports/overview` | KEEP | ARIS CONTROL |
| GET | `/aris3/reports/daily` | KEEP | ARIS CONTROL |
| GET | `/aris3/reports/calendar` | KEEP | ARIS CONTROL |
| POST | `/aris3/exports` | KEEP | ARIS CONTROL |
| GET | `/aris3/exports` | KEEP | ARIS CONTROL |
| GET | `/aris3/exports/{export_id}` | KEEP | ARIS CONTROL |
| GET | `/aris3/exports/{export_id}/download` | KEEP | ARIS CONTROL |
| POST | `/aris3/assets/upload-image` | KEEP | ARIS CONTROL |
| GET | `/aris3/ops/metrics` | HIDE-IN-DOCS | Infra/Dev/Observabilidad |
| GET | `/health` | KEEP | Infra/Dev |
| GET | `/ready` | KEEP | Infra/Dev |

## B) Plan P0 / P1 / P2

### P0 (no-breaking, inmediato)
1. **Documentación de compatibilidad explícita por endpoint**:
   - Añadir `x-compat-rules` con: route-stability, pagination limit/offset, tenant-status case-insensitive input.
2. **Error model homogéneo**:
   - Unificar 4xx/5xx con `ErrorResponse` + `trace_id`.
   - Estándar para `422` (campos: `code`, `message`, `details[]`, `trace_id`).
3. **Headers de trazabilidad y request identity**:
   - `X-Trace-Id` en response siempre.
   - `Idempotency-Key` documentado (al menos en POST/PATCH/PUT/DELETE mutantes).
4. **Validaciones de input sin romper contrato**:
   - Mantener aceptación de estados en minúscula, normalizando a mayúscula internamente.
   - `limit <= 200` en todos los listados con `limit/offset`.

### P1 (cambios menores compatibles)
1. **Marcar operaciones legacy como deprecadas en OpenAPI**:
   - `PATCH /aris3/auth/change-password`.
   - `POST /aris3/stock/import-sku` (si estrategia EPC es oficial).
2. **Consolidar endpoints ocultos de access-control**:
   - Mantener funcionales, pero redirigir documentación y SDK al namespace admin.
3. **Telemetría de uso por endpoint**:
   - Medir clientes reales (CONTROL/OPERADOR/scripts) antes de retirar nada.

### P2 (breaking, solo con evidencia)
1. **Retiro de rutas legacy realmente sin tráfico** (después de 2 ciclos + sunset headers).
2. **Contrato de errores versionado** obligatorio en toda la API.
3. **Racionalización de namespaces** access-control legacy si todo cliente migró.

## C) Snippets OpenAPI (YAML)

### TenantStatus enum
```yaml
components:
  schemas:
    TenantStatus:
      type: string
      description: |
        Canonical values are uppercase. Lowercase is accepted for backward compatibility,
        and normalized server-side.
      enum: [ACTIVE, SUSPENDED, CANCELED]
      x-accepts-case-insensitive: true
      example: ACTIVE
```

### Pagination schema
```yaml
components:
  schemas:
    Pagination:
      type: object
      required: [limit, offset, total]
      properties:
        limit:
          type: integer
          minimum: 1
          maximum: 200
          example: 50
        offset:
          type: integer
          minimum: 0
          example: 0
        total:
          type: integer
          minimum: 0
          example: 1240
```

### ErrorResponse schema
```yaml
components:
  schemas:
    ErrorDetail:
      type: object
      properties:
        field:
          type: string
          example: body.status
        issue:
          type: string
          example: value is not a valid enum member
        ctx:
          type: object
          additionalProperties: true

    ErrorResponse:
      type: object
      required: [code, message, trace_id]
      properties:
        code:
          type: string
          example: VALIDATION_ERROR
        message:
          type: string
          example: Request validation failed
        details:
          type: array
          items:
            $ref: '#/components/schemas/ErrorDetail'
        trace_id:
          type: string
          format: uuid
      example:
        code: VALIDATION_ERROR
        message: Request validation failed
        details:
          - field: query.limit
            issue: ensure this value is less than or equal to 200
        trace_id: 4f6719d2-6fd1-46dd-b92d-09e5d8ed0ad7
```

### Header Idempotency-Key
```yaml
components:
  parameters:
    IdempotencyKeyHeader:
      name: Idempotency-Key
      in: header
      required: false
      schema:
        type: string
        minLength: 8
        maxLength: 128
      description: |
        Client-provided idempotency key for safely retrying mutating requests.
        Recommended for POST/PATCH/PUT/DELETE operations.
```

## D) Notas de implementación FastAPI
1. **Middleware de trace/contexto**
   - Generar `trace_id` (UUID) por request si no viene en `X-Trace-Id`.
   - Guardarlo en `request.state.trace_id` y retornarlo en header + envelope.
2. **Exception handlers globales**
   - `RequestValidationError` → `422` con `ErrorResponse` uniforme.
   - `HTTPException` → mapear a `ErrorResponse` y conservar status.
   - Exception genérica → `500` con código estable (`INTERNAL_ERROR`) y sin filtrar internals.
3. **Validadores de enums compatibles**
   - En Pydantic, normalizar `status.upper()` antes de validar enum canónico.
4. **Validación de paginación reusable**
   - Dependencia común `PaginationParams(limit<=200, offset>=0)` aplicada en todos los listados.
5. **Idempotencia**
   - Para operaciones críticas (actions, create, close/day-close), registrar `Idempotency-Key` + hash body + ventana TTL en Postgres.
   - Si llega la misma llave y payload, devolver misma respuesta (o referencia al resultado previo).

## E) Checklist de pruebas
- Contrato OpenAPI:
  - [ ] Todos los mutantes documentan `Idempotency-Key`.
  - [ ] Todos los listados exponen `limit/offset` con `maximum: 200`.
  - [ ] Todos los errores 4xx/5xx referencian `ErrorResponse`.
- Compatibilidad:
  - [ ] Rutas `/aris3/*` sin cambios.
  - [ ] `status` acepta `active/suspended/canceled` y persiste/retorna `ACTIVE/SUSPENDED/CANCELED`.
  - [ ] ARIS OPERADOR smoke tests (sales/returns/cash/stock/transfers) pasan.
- Observabilidad:
  - [ ] Cada response trae `trace_id` en body o cabecera estandarizada.
  - [ ] Logs correlacionables por `trace_id`.

## F) Lista “no tocar / no romper”
1. No renombrar ni mover rutas existentes `/aris3/*`.
2. No reemplazar `limit/offset` por cursor como contrato por defecto.
3. No cambiar semántica de estados canónicos (mantener MAYÚSCULAS).
4. No remover envelope/traceabilidad en respuestas.
5. No introducir cambios en POS (`pos-sales`, `pos-returns`, `pos-cash`) sin pruebas de regresión de ARIS OPERADOR.
6. No retirar endpoints ocultos/legacy sin telemetría + deprecación formal + ventana de migración.
