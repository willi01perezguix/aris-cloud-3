# Recovery Playbook — ARIS3 Backup/Restore + Release Readiness

## Objetivo
Asegurar recuperación operativa y preparación de release con evidencia verificable y sin romper el contrato ARIS3.

## Pre-requisitos
- Variables:
  - `OPS_ENABLE_BACKUP_DRILL=true`
  - `OPS_ARTIFACTS_DIR` (default `./artifacts`)
  - `OPS_DRILL_TIMEOUT_SEC` (default `120`)
  - `DATABASE_URL` válido para el entorno objetivo
- Dependencias instaladas: `pip install -r requirements.txt`

## Verification Steps (ejecución en orden)

### 1) Pre-deploy checks
1. Confirmar rama de trabajo y estado limpio:
   ```bash
   git branch --show-current
   git status --short
   ```
2. Ejecutar gate de release readiness (sqlite/local):
   ```bash
   python scripts/release_readiness_gate.py --pytest-target tests/smoke/test_post_merge_readiness.py
   ```
3. Validar migraciones en base desechable (incluido en gate). Si se requiere manual:
   ```bash
   alembic upgrade head && alembic downgrade base && alembic upgrade head
   ```

### 2) Deploy checks
1. Ejecutar backup previo al despliegue:
   ```bash
   python scripts/ops/backup_create.py --name pre_deploy_YYYYMMDD_HHMM
   ```
2. Validar manifest del backup:
   ```bash
   python scripts/ops/backup_manifest_validate.py <ruta_manifest.json>
   ```
3. Verificar conectividad del servicio:
   ```bash
   curl -sS http://<host>/health
   curl -sS http://<host>/ready
   ```

### 3) Post-deploy validation
1. Ejecutar smoke crítico:
   ```bash
   pytest -q tests/smoke/test_post_merge_readiness.py
   ```
2. Verificar endpoints críticos:
   ```bash
   curl -sS http://<host>/aris3/stock
   curl -sS http://<host>/aris3/reports/overview
   curl -sS http://<host>/aris3/exports
   ```
3. Confirmar latencia p95 local/CI dentro de presupuesto (default 120ms para `/health`) en resumen del gate.

### 4) Rollback trigger conditions + rollback verification
#### Trigger conditions
- `scripts/release_readiness_gate.py` en `FAIL`.
- `GET /ready` devuelve no-200 o error de DB.
- Smoke crítico rojo en auth/stock/transfers/POS/reports/exports.
- Falla de backup/restore drill o inconsistencia de manifest.

#### Rollback procedure
1. Declarar `NO-GO` y congelar despliegues.
2. Revertir aplicación al último release estable.
3. Restaurar último backup válido:
   ```bash
   python scripts/ops/backup_restore_verify.py <ruta_manifest.json>
   ```
4. Ejecutar verificación post-rollback:
   ```bash
   curl -sS http://<host>/health
   curl -sS http://<host>/ready
   pytest -q tests/smoke/test_post_merge_readiness.py
   ```

## Evidencia requerida
- `manifest.json`
- `drill_report_<timestamp>.json`
- salida del gate `scripts/release_readiness_gate.py`
- salida de smoke `tests/smoke/test_post_merge_readiness.py`
- bitácora de rollback (si aplica)

## Validated Commands (Sprint 6 Day 8)
```bash
python scripts/release_readiness_gate.py --pytest-target tests/smoke/test_post_merge_readiness.py
python scripts/ops/backup_create.py --name pre_deploy_YYYYMMDD_HHMM
python scripts/ops/backup_manifest_validate.py <ruta_manifest.json>
python scripts/ops/backup_restore_verify.py <ruta_manifest.json>
python scripts/post_go_live_integrity_check.py --strict
```
