# Changelog

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
