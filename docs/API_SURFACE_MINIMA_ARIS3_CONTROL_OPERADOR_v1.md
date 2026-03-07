# ARIS-CLOUD-3 — Propuesta de API Surface mínima (CONTROL vs OPERADOR)

## Suposiciones explícitas
1. El uso real de cliente se infiere por contratos/rutas y pruebas del repositorio (no por telemetría productiva en vivo).
2. ARIS CONTROL usa las rutas `/aris3/admin/*` y `/aris3/admin/access-control/*` para gestión y permisos efectivos.
3. ARIS OPERADOR depende de autenticación/self-permissions y no debe consumir la superficie administrativa.
4. No se introduce cambio de shape ni eliminación inmediata; solo clasificación, deprecación gradual y alias.

---

## A) Mapa “Usado hoy vs No usado hoy” por cliente

### ARIS OPERADOR (crítico, no romper)

**Usado hoy (obligatorio mantener):**
- `POST /aris3/auth/login`
- `POST|PATCH /aris3/auth/change-password` (al menos un método, mantener compatibilidad)
- `GET /aris3/me`
- `GET /aris3/access-control/effective-permissions` (self)
- `GET /aris3/access-control/permission-catalog` (self)
- `GET /health`, `GET /ready`

**No usado hoy / no requerido para operación diaria:**
- Toda la superficie `/aris3/admin/*`
- Rutas ACL legacy ocultas fuera de schema (`/aris3/access-control/...` con tenant/store/user path params)

### ARIS CONTROL (admin desktop)

**Usado hoy (core funcional):**
- Gestión entidad:
  - `GET/POST/PATCH/DELETE /aris3/admin/tenants`
  - `POST /aris3/admin/tenants/{tenant_id}/actions`
  - `GET/POST/PATCH/DELETE /aris3/admin/stores`
  - `GET/POST/PATCH/DELETE /aris3/admin/users`
- ACL admin (para checkbox/overrides y cálculo efectivo):
  - `GET /aris3/admin/access-control/permission-catalog`
  - `GET /aris3/admin/access-control/role-templates/{role_name}`
  - `PUT /aris3/admin/access-control/role-templates/{role_name}`
  - `GET|PATCH /aris3/admin/access-control/user-overrides/{user_id}`
  - `GET /aris3/admin/access-control/effective-permissions?user_id=...`

**Uso opcional hoy (dependiendo de modelo de negocio):**
- `GET|PATCH /aris3/admin/access-control/tenant-role-policies/{role_name}`
- `GET|PATCH /aris3/admin/access-control/store-role-policies/{store_id}/{role_name}`
- `GET|PATCH /aris3/admin/settings/variant-fields`
- `GET|PATCH /aris3/admin/settings/return-policy`

---

## B) Propuesta P0 / P1 / P2

### P0 (non-breaking, recomendado inmediato)
1. **Congelar Core obligatorio** (lista sección C) y etiquetar en OpenAPI con tag `core`.
2. **Unificar comportamiento `change-password`**:
   - Mantener `POST` y `PATCH` apuntando al mismo handler (ya ocurre).
   - Marcar `PATCH` como `deprecated: true` (o POST, según cliente principal) y documentar método canónico.
3. **Paginación robusta en `/admin/tenants|stores|users`:**
   - mantener `limit<=200`, `offset>=0`.
   - `pagination.total` siempre desde `count(*)` con mismos filtros.
   - si `offset > total`, devolver `[]` + `pagination` consistente (sin error).
4. **Hardening anti “faltan registros >200”**:
   - guía explícita para UI: iterar páginas hasta `offset + count >= total`.
   - agregar ejemplo OpenAPI para recorrido completo.

### P1 (deprecations + hardening)
1. Marcar como `deprecated` las rutas ACL legacy ocultas con path tenant/store/user (mantener runtime).
2. Mantener overlays tenant/store pero etiquetarlos `advanced` y `x-internal: true` cuando no se usen en CONTROL.
3. Normalizar documentación de seguridad por endpoint (`BearerAuth`, scopes/permiso requerido).
4. Añadir encabezado/referencia uniforme de trazabilidad (`trace_id`) en ejemplos exitosos y de error.

### P2 (cleanup real, posible v2)
1. Consolidar ACL de administración en un único árbol v2 (sin rutas duplicadas legacy).
2. Opcional: remover overlays tenant/store **solo en v2** y conservar semántica vía templates + overrides (ver sección G).
3. Migrar completamente alias de `change-password` al método canónico y retirar el deprecado en v2.

---

## C) Endpoints obligatorios a mantener

### Operación mínima (OPERADOR)
- `POST /aris3/auth/login`
- `POST /aris3/auth/change-password` (canónico)
- `PATCH /aris3/auth/change-password` (alias temporal)
- `GET /aris3/me`
- `GET /aris3/access-control/effective-permissions`
- `GET /aris3/access-control/permission-catalog`
- `GET /health`
- `GET /ready`

### Administración mínima (CONTROL)
- `GET/POST/PATCH/DELETE /aris3/admin/tenants`
- `POST /aris3/admin/tenants/{tenant_id}/actions`
- `GET/POST/PATCH/DELETE /aris3/admin/stores`
- `GET/POST/PATCH/DELETE /aris3/admin/users`
- `GET /aris3/admin/access-control/permission-catalog`
- `GET|PUT /aris3/admin/access-control/role-templates/{role_name}`
- `GET|PATCH /aris3/admin/access-control/user-overrides/{user_id}`
- `GET /aris3/admin/access-control/effective-permissions`

---

## D) Endpoints a deprecate / ocultar (sin romper inmediato)

### Deprecar (soft)
- `PATCH /aris3/auth/change-password` (si POST queda canónico; o viceversa).
- Rutas ACL legacy hidden en `/aris3/access-control/*` con parámetros tenant/store/user para resolución de terceros.

### Internal only (mantener pero no promover en contrato público)
- `/aris3/auth/token` (Swagger/password-flow técnico).
- `/aris3/admin/access-control/tenant-role-policies/{role_name}`
- `/aris3/admin/access-control/store-role-policies/{store_id}/{role_name}`
  - pasar a tag `internal` si CONTROL no las usa activamente.

---

## E) Recomendaciones exactas de OpenAPI 3.1

1. **Marcar deprecaciones**
   - `deprecated: true` en rutas/métodos alias.
   - descripción con fecha objetivo de retiro (solo v2).
2. **Tags por producto/superficie**
   - `operator-core`, `admin-core`, `admin-advanced`, `internal`.
3. **Security explícita por operación**
   - `security: [{BearerAuth: []}]` + nota de permiso requerido (`USER_MANAGE`, `STORE_VIEW`, etc.).
4. **Ejemplos obligatorios**
   - login, effective permissions self, user overrides, list paginado multi-página.
5. **Paginación estandarizada**
   - ejemplo de respuesta para `offset > total` devolviendo array vacío y `pagination.total` intacto.
6. **Vendor extensions sugeridas**
   - `x-aris-stability: core|advanced|internal`
   - `x-aris-client: control|operador|both`

---

## F) Checklist de pruebas

### Unit tests (backend)
- Paginación:
  - `limit/offset` en tenants, stores, users.
  - `offset > total` retorna `[]` y `pagination` consistente.
  - `total` consistente con filtros (`status`, `search`, `role`, `store_id`, `tenant_id`).
- Scopes:
  - deny cross-tenant y store mismatch.
  - superadmin sin tenant filter ve global.
- ACL:
  - effective-permissions respeta precedencia template → overlays → user-overrides.
  - user-overrides deny prevalece sobre allow heredado.

### Pruebas manuales CONTROL
1. Login admin.
2. Listar tenants/stores/users con dataset >200 y paginar hasta completar `total`.
3. Aplicar override por usuario y validar cambio inmediato en effective-permissions.
4. Verificar que overlays (si habilitados) se reflejan en trazabilidad de fuentes.

### Pruebas manuales OPERADOR
1. Login operador.
2. `GET /aris3/me` correcto.
3. `GET /aris3/access-control/effective-permissions` y `permission-catalog` correctos.
4. Cambio de contraseña vía método canónico.
5. Confirmar que no hay regresión en flujos diarios (sin acceso admin).

---

## G) Si se eliminan overlays tenant/store (solo v2), cómo mantener effective-permissions

### Modelo objetivo simplificado
1. **Role template** (base por rol) permanece.
2. **User overrides** permanece (allow/deny por usuario).
3. Se elimina capa intermedia tenant/store overlay.

### Resolución propuesta
- `effective = template(role)`
- aplicar `user.allow` (union)
- aplicar `user.deny` (sustracción con prioridad final)
- exponer `sources_trace` solo con `template` y `user`.

### Estrategia de migración sin ruptura
1. Inventariar overlays tenant/store activos.
2. Materializar overlays a overrides de usuario (batch por tenant/store).
3. Correr validación de paridad (`effective_before == effective_after`) por usuario.
4. Congelar escritura de overlays en v1 (`deprecated + internal only`).
5. Eliminar físicamente overlays en v2 tras ventana de convivencia.

---

## Nota de riesgo principal
El problema “no aparecen todos los stores/users” no se resuelve quitando paginación; se resuelve **consumiéndola correctamente** con iteración de páginas y `total` consistente. El backend actual ya está alineado con ese contrato y debe mantenerse.
