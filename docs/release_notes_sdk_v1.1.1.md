# Release Notes SDK v1.1.1

## Estado de release
- **Decisión final:** GO (Day 10).
- **Tipo:** release estable `v1.1.1`.
- **Impacto:** mejora resiliencia y observabilidad del SDK sin romper contratos existentes.

## Fixes incluidos (Day 9 + cierre Day 10)
- Telemetría de polling por estado en `wait_for_export_ready` con `telemetry_hook` opcional.
- Retries idempotentes con jitter configurable (`ARIS3_RETRY_JITTER_*`) manteniendo defaults backward-compatible.
- CLI de smoke post-release con salida de artifacts configurable (`--artifacts-dir`, `--suite-name`).
- Consistencia de versión y empaquetado final de `aris3-client-sdk` a `1.1.1`.

## No-regresiones verificadas
- Se preserva configuración estricta: `ARIS3_API_BASE_URL` sigue siendo obligatoria.
- Polling de exports mantiene bypass de cache por request (`use_get_cache=False`) sin side-effects globales.
- Endpoint por defecto operativo para runtime/documentación: `ARIS3_BASE_URL=https://aris-cloud-3-api-pecul.ondigitalocean.app/`.

## Evidencia técnica
- `pytest ./clients/python/tests -q` en verde.
- `python ./clients/python/scripts/release_gate.py` en verde.
- Smoke en entorno limpio (venv nuevo) documentado en `docs/v1.1.1_day10_smoke.md`.
- Artefactos de distribución generados:
  - `clients/python/aris3_client_sdk/dist/aris3_client_sdk-1.1.1.tar.gz`
  - `clients/python/aris3_client_sdk/dist/aris3_client_sdk-1.1.1-py3-none-any.whl`

## Impacto para usuarios
- Mayor capacidad de diagnóstico en polling de exports por eventos de telemetría.
- Menor riesgo de tormentas de reintento en escenarios transitorios (jitter opcional).
- Proceso de validación post-release repetible mediante CLI smoke y plan de monitoreo 72h.
