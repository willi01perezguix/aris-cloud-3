# Day 7 — Plan Hotfix (NO-GO) para habilitar salida estable v1.0.3

Fecha: 2026-02-14
Estrategia: mantener RC + cerrar bloqueadores críticos de publicación estable.

## Checkpoint Δ1 — Branch y ownership
- Δ Hotfix branch: `hotfix/v1.0.3-release-gate`.
- Δ Owners: Release Engineering + QA + Operaciones.
- Δ Alcance permitido: pipeline de empaquetado, validación operativa, evidencia release.
- Δ Alcance prohibido: cambios de contrato API/endpoints/payloads.

## Checkpoint Δ2 — Plan de corrección
| ID | Acción | Responsable | ETA máxima | Salida esperada |
|---|---|---|---|---|
| HF-01 | Ejecutar `preflight_release.ps1` y `build_control_center.ps1` en host Windows release | Release Eng | T+2h | `dist/ARIS_CONTROL_2.exe` |
| HF-02 | Generar SHA256 y archivo `ARIS_CONTROL_2.exe.sha256` | Release Eng | T+2h15m | Hash trazable publicado |
| HF-03 | Publicar release candidate evidenciado para re-gate interno (sin marcar estable aún) | Release Eng | T+2h30m | Asset descargable interno |
| HF-04 | Ejecutar smoke T+0 real en máquina limpia (abrir/login/tenant-store-user/API) | QA + Operador SUPERADMIN | T+4h | Reporte PASS/FAIL por paso |
| HF-05 | Ejecutar rollback drill real v1.0.3-rc -> v1.0.2 estable | Operaciones | T+5h | Acta rollback <15 min |
| HF-06 | Reunión de re-gate y decisión final GO/NO-GO | PM + QA + Ops | T+6h | Acta firmada |

## Checkpoint Δ3 — Criterios de salida del hotfix
1. Δ `.exe` generado en Windows y ejecuta sin crash inicial.
2. Δ SHA256 coincide entre archivo local y asset publicado.
3. Δ Smoke T+0: todos los pasos en PASS.
4. Δ Rollback drill real ejecutado dentro de SLA (<15 min).
5. Δ Riesgos críticos abiertos = 0.

## Checkpoint Δ4 — Resultado esperado
- Δ Si todos los criterios se cumplen: cambiar estado a **GO** y publicar estable `v1.0.3`.
- Δ Si falla cualquier criterio: mantener **NO-GO**, conservar RC y abrir siguiente iteración hotfix.
