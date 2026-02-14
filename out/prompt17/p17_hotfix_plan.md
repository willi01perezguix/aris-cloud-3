# ARIS_CONTROL_2 — Hotfix Plan (post NO-GO Day 7)

## Branch propuesta
- `hotfix/v1.0.4-packaging-smoke-windows`

## Objetivo
Cerrar bloqueos críticos que impiden publicar estable `v1.0.4`:
1. Build reproducible de `ARIS_CONTROL_2.exe` en runner Windows compatible.
2. Verificación SHA256 del binario generado.
3. Smoke T+0 en máquina limpia con evidencia PASS.

## Acciones
1. Preparar runner Windows con `pwsh` y `PyInstaller` preinstalado (o mirror interno permitido).
2. Ejecutar pipeline de empaquetado RC y generar artefacto `ARIS_CONTROL_2.exe`.
3. Calcular hash SHA256 y guardar evidencia en reporte de build.
4. Ejecutar smoke mínimo:
   - abre `.exe`
   - login OK
   - flujo base Tenant/Store/User según permisos
   - conectividad API al endpoint por defecto
5. Re-ejecutar gate Day 7 y emitir nueva acta GO/NO-GO.

## Criterio de salida del hotfix
- Build: PASS
- Hash: PASS
- Smoke T+0: PASS
- Riesgos críticos R1/R2: cerrados
- Habilita promoción a release estable `v1.0.4`
