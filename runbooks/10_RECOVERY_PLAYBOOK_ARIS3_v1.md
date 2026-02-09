# Recovery Playbook — ARIS3 Backup/Restore Drill

## Objetivo
Validar que los backups operativos son reproducibles, verificables y auditables sin romper contrato.

## Pre-requisitos
- Variables:
  - `OPS_ENABLE_BACKUP_DRILL=true`
  - `OPS_ARTIFACTS_DIR` (default `./artifacts`)
  - `OPS_DRILL_TIMEOUT_SEC` (default `120`)
- Acceso a la base de datos configurada en `DATABASE_URL`.

## 1) Crear backup
```bash
python scripts/ops/backup_create.py --name backup_drill_YYYYMMDD
```
- Salida: ruta al `manifest.json` dentro de `OPS_ARTIFACTS_DIR/<backup_name>/`.
- Se escribe un evento de auditoría `backup.create` (si existe tenant).

## 2) Validar manifest
```bash
python scripts/ops/backup_manifest_validate.py <ruta_manifest.json>
```
Si falla, revisar checksums y rutas en el directorio del backup.

## 3) Restore + verify en DB temporal
```bash
python scripts/ops/backup_restore_verify.py <ruta_manifest.json>
```
Salida: ruta al `artifacts/drill_report_<timestamp>.json`.

## 4) Interpretar reporte
En el reporte:
- `row_counts_match`: `true` si los conteos restaurados coinciden con el manifest.
- `sanity_checks.primary_keys_non_null`: `true` si no hay PK nulas.
- `status`: `PASS` o `FAIL`.

## 5) Rollback plan
Si `status=FAIL`:
1. Detener el proceso de restore.
2. Re-ejecutar validación del manifest.
3. Si el manifest es válido, repetir el restore con un nuevo `OPS_ARTIFACTS_DIR`.
4. Si persiste, escalar con el reporte y el manifest.

## 6) Evidencia
Guardar:
- `manifest.json`
- `drill_report_<timestamp>.json`
- Bitácora de ejecución (salida CLI)

