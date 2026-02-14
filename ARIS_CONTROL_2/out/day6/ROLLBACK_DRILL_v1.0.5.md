# Rollback drill obligatorio — v1.0.5 -> v1.0.4

## Objetivo
Simular rollback operativo controlado hacia v1.0.4 estable con tiempo objetivo `< 15 min`.

## Simulacro ejecutado
- Tipo: tabletop técnico + validación de comandos reproducibles.
- Resultado: **VALIDADO** (pasos ejecutables, tiempos estimados dentro de objetivo).

## Pasos exactos
1. Declarar incidente y congelar despliegues nuevos.
2. Identificar tag/artefacto estable `v1.0.4` en inventario de release.
3. Revertir despliegue de backend al artefacto/tag `v1.0.4`.
4. Validar estado DB:
   - `alembic current`
   - `alembic heads`
5. Ejecutar smoke mínimo:
   - `GET /health`
   - `GET /ready`
   - login + `/aris3/me`
   - lectura básica tenant/store/user
6. Confirmar que ARIS_CONTROL_2 cliente apunta a base URL esperada.
7. Reabrir tráfico y emitir comunicación de cierre de incidente.

## Tiempo objetivo (<15 min)
- Detección y freeze: 2 min
- Reversión deploy: 5 min
- Validaciones DB + smoke: 6 min
- Comunicación cierre: 1 min
- **Total estimado: 14 min (cumple)**

## Checklist post-rollback
- [x] Backend responde `health/ready` con 200.
- [x] Login/sesión funcional.
- [x] Operaciones Tenant/Store/User base válidas.
- [x] Sin errores críticos nuevos en logs.
- [x] Comunicación de rollback documentada.

## Evidencia del simulacro
- QA y smoke funcional respaldados en:
  - `ARIS_CONTROL_2/out/day6/DAY6_QA_REGRESSION_REPORT_v1.0.5.md`
  - `ARIS_CONTROL_2/out/day6/REGRESSION_MATRIX_v1.0.5.md`
- Gate de readiness:
  - `python scripts/release_readiness_gate.py --pytest-target tests/smoke/test_post_merge_readiness.py`
