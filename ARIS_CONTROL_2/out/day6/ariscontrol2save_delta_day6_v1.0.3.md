# ariscontrol2save — delta-only Day 6 (v1.0.3)

## Δ Código
1. `ARIS_CONTROL_2/aris_control_2/app/diagnostics.py`
   - `APP_VERSION` actualizado de `v1.0.2-dev` a `v1.0.3-rc`.
2. `clients/python/tools/create_support_bundle.py`
   - Hardening de redacción: cualquier env `ARIS3_*` con marcador sensible (`TOKEN/SECRET/PASSWORD/AUTH/KEY`) se exporta como `<REDACTED>`.
3. `ARIS_CONTROL_2/tests/unit/test_day1_kickoff_quickwins.py`
   - Ajuste de prueba para firma actual de `_run_listing_loop(..., filter_keys=...)` y mensaje de refresh con paginación.
4. `clients/python/tests/test_release_hardening.py`
   - Nueva prueba de regresión para validar redacción de claves sensibles en support bundle.

## Δ Evidencia QA/Regresión
- Suite ARIS_CONTROL_2 unit+integration: PASS (95/95).
- Suite clients/python control_center+integration+release_hardening: PASS (21/21).
- QA matrix smoke: PASS con SKIP autenticados esperados por falta de credenciales.

## Δ Packaging RC
- Verificación de scaffold packaging: PASS.
- Build `.exe` Windows: BLOCKED en CI Linux (sin `pwsh`/`PyInstaller`).

## Δ Riesgo residual
- Pendiente gate final en runner Windows release para binario `.exe`, smoke de arranque y SHA256 final.
