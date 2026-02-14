# Release notes draft — ARIS_CONTROL_2 v1.0.3 (RC)

## Mejoras principales
- Hardening final de QA/regresión para flujos críticos de sesión, tenant context y guardrails admin.
- Panel de diagnóstico alineado a versión `v1.0.3-rc` y validación de telemetría/observabilidad.
- Export de soporte reforzado con redacción explícita de variables sensibles `ARIS3_*`.

## Fixes
- Actualizado test legacy de listado admin para mantener compatibilidad con firma actual (`filter_keys`) y mensaje de refresh con paginación.
- Se mantiene trazabilidad estandarizada de errores en formato `code/message/trace_id`.

## Riesgos conocidos
- Packaging RC Windows (`.exe`) y smoke de arranque en host Windows siguen pendientes por limitación de entorno CI Linux.
- QA matrix autenticada completa depende de credenciales operativas y tenant seed en entorno release.

## Contrato API
- **Sin cambios de contrato API**: no se alteraron endpoints, payloads ni reglas de backend.

## Gate recomendado para pasar a estable
1. Ejecutar scripts oficiales de packaging en runner Windows.
2. Adjuntar hash SHA256 definitivo del `.exe` en evidencia release.
3. Ejecutar smoke guiado autenticado (SUPERADMIN + flujo tenant/store/user).
