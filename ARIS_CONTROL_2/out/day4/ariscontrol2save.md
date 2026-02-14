# ariscontrol2save — v1.0.3 Day 4 (delta-only)

## Cambios aplicados
- Se agregó `SessionGuard` global para módulos protegidos, con validación de token ausente/corrupto/expirado y redirección controlada a login.
- Se unificó manejo de `401/403` en `HttpClient` mediante handler central:
  - `401`: logout seguro + preservación de contexto temporal + aviso de sesión.
  - `403`: sesión se mantiene + aviso claro de acceso denegado.
- Se incorporó almacenamiento temporal de contexto de recuperación auth (`módulo`, `tenant`, `filtros`, `paginación`) y restauración post-login compatible con scope.
- Se robusteció `logout` para limpieza total de estado sensible local (tokens + contexto auth temporal + contexto operativo persistido).
- Se estandarizó payload de error visible con `status_code` además de `code/message/trace_id`.

## Riesgos
- Validación de expiración depende de claim `exp` JWT; si un proveedor emite token sin `exp`, se considera válido hasta próximo `401` del backend.

## Rollback simple
1. Revertir commit Day 4.
2. Verificar que `HttpClient` no tenga `auth_error_handler`.
3. Verificar que `main` use chequeos de sesión previos y `session.clear()` en logout.
4. Ejecutar smoke básico de login/admin/logout.
