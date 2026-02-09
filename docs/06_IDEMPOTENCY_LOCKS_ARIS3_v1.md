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

