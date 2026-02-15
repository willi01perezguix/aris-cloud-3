# Release Notes SDK v1.1.0

## Resumen ejecutivo
La versión **v1.1.0** del SDK de Python queda cerrada con gate final de calidad en verde para suite de `clients/python/tests`, verificación del release gate técnico y validación de empaquetado (sdist + wheel).

## Cambios principales
- Configuración estricta: `ARIS3_API_BASE_URL` es obligatoria vía entorno, sin fallback runtime.
- Polling de exports con lectura fresca por request para evitar respuestas stale por cache compartido.
- Endurecimiento de validaciones de configuración y modelos del SDK.
- Evidencia de calidad para CI matrix/release gate orientada a no-regresión.

## Compatibilidad (breaking / non-breaking)
- **Breaking (configuración):** instalaciones que dependían de fallback implícito de `ARIS3_API_BASE_URL` ahora deben declarar la variable de entorno explícitamente.
- **Non-breaking:** mejoras de robustez en polling de exports y validaciones; no cambia la superficie pública principal de clientes.

## Guía corta de upgrade
1. Actualizar dependencia a `aris3-client-sdk==1.1.0`.
2. Definir `ARIS3_API_BASE_URL` en el entorno de ejecución (CI/local/runtime).
3. Ejecutar smoke rápido:
   - import del paquete
   - `load_config()` con env presente
   - flujo mínimo de exports en ambiente de pruebas

## Evidencia de calidad y empaquetado
- `pytest clients/python/tests -q` en verde.
- `python clients/python/scripts/release_gate.py` en verde.
- Artefactos generados:
  - `clients/python/aris3_client_sdk/dist/aris3_client_sdk-1.1.0.tar.gz`
  - `clients/python/aris3_client_sdk/dist/aris3_client_sdk-1.1.0-py3-none-any.whl`
- Metadatos validados en artefactos (`Name`, `Version`, `Requires-Python`, `Requires-Dist`).

## Checklist de rollback
- Mantener tag previo estable disponible (ejemplo: `v1.1.0-rc` o último estable interno).
- Si se detecta incidencia productiva:
  1. Revertir pin de dependencia a versión anterior aprobada.
  2. Re-ejecutar smoke de configuración y exports.
  3. Abrir hotfix sobre `main` con evidencia de regresión y prueba mínima reproducible.

## Workflows relevantes a vigilar en PR
- `.github/workflows/clients-python-sdk.yml`
- `.github/workflows/clients-packaging-smoke.yml`
- `.github/workflows/release-readiness.yml`
- `.github/workflows/ga-release-gate.yml`
