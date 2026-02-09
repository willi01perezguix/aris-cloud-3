# Auditoría, Observabilidad y Seguridad — ARIS3

## Logging estructurado (JSON)
Cada request registra un evento JSON con:
- `trace_id`
- `tenant_id`
- `user_id`
- `route`
- `method`
- `status_code`
- `latency_ms`
- `db_time_ms` (si aplica)
- `error_code`
- `error_class`

## Redacción de secretos
- No se incluyen tokens, passwords ni headers sensibles en logs.
- En errores no controlados se reporta solo `type` de excepción para evitar filtrado accidental.

## Trazabilidad de auditoría
- Los eventos de auditoría (`audit_events`) incluyen `trace_id`.
- Para mutaciones críticas, la correlación `trace_id` + audit event permite reconstruir flujo.

## Métricas operativas
- `http_requests_total` y `http_request_duration_ms` por ruta/método/status.
- `idempotency_replay_total` para replays.
- `lock_wait_timeout_total` para timeouts de bloqueo.
- `rbac_denied_total` para denegaciones.
- `invariants_violation_total` por tipo de invariante.

## Endpoint interno de métricas
Si `METRICS_ENABLED=true`, se expone:
- `GET /aris3/ops/metrics` (uso interno, documentado para observabilidad).

