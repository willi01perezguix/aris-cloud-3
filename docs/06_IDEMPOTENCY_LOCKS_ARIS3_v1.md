# Idempotencia y Locks Operativos — ARIS3

## Idempotencia
- Las mutaciones críticas requieren `Idempotency-Key`.
- Replays exitosos incrementan `idempotency_replay_total`.
- Errores se registran con `code/message/details/trace_id`.

## Locks y timeouts
- Los timeouts de lock se reportan como `LOCK_TIMEOUT`.
- Se incrementa el contador `lock_wait_timeout_total`.
- Los errores se devuelven con payload estándar y `trace_id`.

## Observabilidad de RBAC
- Denegaciones de permisos incrementan `rbac_denied_total`.

## Evidencias Sprint 4 Día 7
- Pruebas de idempotencia y auditoría ejecutadas vía `pytest` (suite estándar).
- Locks de concurrencia validados por métricas y manejo de `LOCK_TIMEOUT` en errores estándar.
- Reporte consolidado en `artifacts/release_candidate/test_matrix_summary.json`.
