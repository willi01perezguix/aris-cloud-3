# Changelog

## v1.1.1 (stable)

- Cierre de release Day 10 completado con gate técnico final en verde (`pytest` + `release_gate.py`) y decisión formal **GO**.
- Versionado del SDK consolidado en `1.1.1` como fuente única desde `pyproject.toml` y verificación de artefactos de distribución (`sdist` + `wheel`).
- Evidencia operativa agregada para smoke en entorno limpio y plan de monitoreo post-release de 72h.

## v1.1.1 Day 9

- Top 3 P0 ejecutados: telemetría opcional de polling de exports, retries con jitter configurable y CLI smoke post-release con argumentos de salida.
- `wait_for_export_ready` ahora puede emitir eventos de estado/latencia por `telemetry_hook` sin romper compatibilidad.
- `ClientConfig` incorpora configuración de jitter en retries (`ARIS3_RETRY_JITTER_*`) manteniendo defaults backward-compatible.
- Se agregan pruebas de cobertura para telemetría de polling, jitter y ejecución CLI con artifact JSON/log.

## v1.1.0

- Configuración estricta del SDK: `load_config` requiere `ARIS3_API_BASE_URL` (sin fallback implícito en runtime).
- Polling de exports endurecido para leer estado fresco por request (`use_get_cache=False` en `wait_for_export_ready`), evitando side-effects por cache global.
- Validaciones de configuración y contratos del SDK endurecidos con cobertura de regresión en `clients/python/tests`.
- Calidad de release reforzada con matrix de CI para SDK y release gate reproducible previo a publicación.

## v1.1.0-rc

- Configuración estricta del SDK: `load_config` requiere `ARIS3_API_BASE_URL` (sin fallback implícito).
- Polling de exports endurecido para leer estado fresco por request (`use_get_cache=False` en `wait_for_export_ready`).
- Hardening de validaciones y cobertura de regresión en el suite de tests de `clients/python/tests`.
- Mejoras de CI para release candidate técnico: matrix Ubuntu/Windows y release gate reproducible.
