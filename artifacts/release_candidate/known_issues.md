# Known Issues — Sprint 4 Día 7

## Bloqueadores (NO-GO)
1. Test matrix sqlite/postgres incompleto (pytest terminado por SIGTERM; requiere ejecución completa).
2. Integrity scan fallido por base de datos sin migraciones/seed (`tenants` inexistente).
3. Backup/restore drill fallido por falta de datos en DB.
4. UAT E2E no ejecutado en ambiente final.
5. Performance smoke no ejecutado (sin base URL).
6. Security gate con WARN (dependencias sin audit y chequeo RBAC incompleto).

## Mitigación
- Ejecutar migraciones y seed en entorno UAT/RC.
- Re-ejecutar `scripts/ops/test_matrix.py` en sqlite y postgres con tiempo suficiente.
- Ejecutar `python -m app.ops.integrity_scan` y backup/restore drill con base poblada.
- Proveer `--base-url` para performance smoke y re-ejecutar.
- Instalar `pip-audit` o herramienta equivalente para el dependency scan.
