# Release notes draft — ARIS_CONTROL_2 v1.0.4 (RC)

## Mejoras clave
- Cierre técnico Day 6 con QA integral y regresión completa en suites unitarias/integración del cliente ARIS_CONTROL_2.
- Regresión backend ARIS Cloud 3 validada en 251 pruebas sin fallos.
- Consolidación documental de matriz de regresión, drill de rollback y memo GO/NO-GO para gate Day 7.

## Fixes
- Hardening pre-release de evidencias operativas: reportes de QA, RC y rollback actualizados a baseline v1.0.4.
- Confirmación de continuidad de guardrails de sesión, tenant context, RBAC visual, idempotencia UI y export CSV filtrado.

## Riesgos conocidos
- Build Windows `.exe` y smoke de arranque RC bloqueados en CI Linux por ausencia de PowerShell (`pwsh`) y PyInstaller.
- Smoke manual remoto contra endpoint por defecto bloqueado por proxy/red (`CONNECT tunnel failed: 403`) en entorno CI.

## Contrato API
- **Sin cambios de contrato API**: no se modificaron endpoints, payloads ni reglas backend.

## Gates pendientes para release final
1. Ejecutar build RC y smoke en host Windows limpio.
2. Registrar tamaño/timestamp/SHA256 del `.exe` generado.
3. Adjuntar evidencia del smoke manual autenticado con credenciales operativas.
