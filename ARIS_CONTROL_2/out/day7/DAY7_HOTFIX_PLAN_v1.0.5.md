# Day 7 — Hotfix Plan v1.0.5 (post NO-GO)

Fecha: 2026-02-14  
Estado inicial: RC mantenido por bloqueo crítico de release.

## Checkpoint Δ1 — Branch propuesta
- Δ `hotfix/v1.0.5-release-gate-windows-packaging`

## Checkpoint Δ2 — Objetivo del hotfix
Cerrar bloqueadores críticos para habilitar publicación estable:
1. Build oficial Windows del binario `ARIS_CONTROL_2.exe`.
2. Hash SHA256 verificable y adjunto.
3. Smoke T+0 en máquina limpia con flujo base completo.
4. Re-gate formal GO/NO-GO con evidencia cerrada.

## Checkpoint Δ3 — Plan de ejecución
| ID | Acción | Responsable | ETA objetivo | Evidencia de salida |
|---|---|---|---|---|
| HF-01 | Ejecutar `scripts/windows/preflight_release.ps1` | Release Eng | T+1h | Preflight PASS |
| HF-02 | Ejecutar `scripts/windows/build_control_center.ps1` | Release Eng | T+2h | `dist/ARIS_CONTROL_2.exe` |
| HF-03 | Calcular hash con `Get-FileHash -Algorithm SHA256` | Release Eng | T+2h15m | `ARIS_CONTROL_2.exe.sha256` |
| HF-04 | Publicar RC interno con asset + hash para validación | Release Eng | T+2h30m | URL de artefacto interno |
| HF-05 | Ejecutar smoke T+0 real en máquina limpia | QA + Operación | T+4h | reporte PASS/FAIL con evidencia |
| HF-06 | Ejecutar rollback drill real (`v1.0.5-rc` -> `v1.0.4`) | Operaciones | T+5h | acta con tiempo total |
| HF-07 | Reunión re-gate y decisión final | PM + QA + Ops | T+6h | nueva acta GO/NO-GO |

## Checkpoint Δ4 — Criterios de salida
- Δ `.exe` generado y ejecutable en Windows limpio.
- Δ SHA256 coincide entre archivo local y asset publicado.
- Δ Smoke T+0: PASS en todos los pasos.
- Δ Rollback drill real <15 minutos.
- Δ Riesgos críticos abiertos: 0.
