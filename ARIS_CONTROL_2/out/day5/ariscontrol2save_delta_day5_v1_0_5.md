# ariscontrol2save — delta-only Day 5 (v1.0.5)

## Δ Cambios aplicados
- `clients/aris3_client_sdk/http_client.py`: retry corto con backoff incremental para `GET` únicamente; mutaciones (`POST/PUT/PATCH/DELETE`) quedan sin retry automático.
- `clients/aris3_client_sdk/config.py` + `.env.example`: nuevos flags operativos `ARIS3_RETRY_MAX_ATTEMPTS` y `ARIS3_RETRY_BACKOFF_MS`.
- `app/admin_console.py`: mejora de estabilidad en navegación rápida y tenant switch (reset de estado dependiente + invalidación de caché), persistencia de contexto sin escrituras redundantes, e indicadores operativos por vista (`última actualización`, `duración carga aprox`, `salud vista: OK/DEGRADED/OFFLINE`).
- `app/state.py`: limpieza automática de contexto operativo al detectar cambio de tenant/rol durante `apply_me`.
- `tests/unit/test_day5_state_and_network_resilience.py`: cobertura para estabilidad de estado, preservación de contexto tras error/reintento y política de retry (GET sí, mutaciones no).

## Captura before/after (texto operativo)
- Before: en fallas transitorias de red el operador no veía estado de salud de vista ni señal de recuperación explícita.
- After: la vista reporta salud `OFFLINE/DEGRADED/OK`, muestra duración de carga y mensaje de recuperación tras retry exitoso.

## Riesgos conocidos
- Si `ARIS3_RETRY_MAX_ATTEMPTS` se sube demasiado, puede aumentar latencia percibida en `GET` degradados.

## Rollback simple
1. `git revert <commit_day5_v1_0_5>`
2. (Opcional) remover variables `ARIS3_RETRY_MAX_ATTEMPTS`/`ARIS3_RETRY_BACKOFF_MS` del entorno.

## No-delta (explícito)
- Sin cambios de endpoints, payloads o reglas de backend.
- Sin cambios de contrato API.
