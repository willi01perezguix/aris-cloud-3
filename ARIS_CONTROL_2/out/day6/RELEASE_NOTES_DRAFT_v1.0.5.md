# Draft Release Notes — v1.0.5

## Resumen
Release candidate orientado a cierre técnico pre-release final (QA/regresión + hardening operacional), sin cambios de contrato API.

## Mejoras / fixes
1. Consolidación de validación Day 6 con suite backend completa y smoke crítico.
2. Regresión dirigida sobre login/sesión, tenant context, acciones sensibles, idempotencia UI, diagnóstico/exportes y estado de filtros/paginación.
3. Actualización de documentación operativa de rollback y decisión GO/NO-GO para Day 7.

## Riesgos conocidos
1. Build oficial Windows `.exe` no ejecutable en entorno Linux actual (falta `pwsh`).
2. Advertencia de paridad Postgres en release gate cuando `POSTGRES_GATE_URL` no está disponible.
3. Un test no crítico de cliente (`test_day1_kickoff_quickwins`) con discrepancia menor de filtros cacheados.

## Guía breve de rollback
1. Congelar despliegues y declarar incidente.
2. Revertir backend a tag estable `v1.0.4`.
3. Validar `alembic current/heads`.
4. Ejecutar smoke mínimo (`/health`, `/ready`, login `/aris3/me`, flujo Tenant/Store/User).
5. Comunicar estado y cerrar incidente.
