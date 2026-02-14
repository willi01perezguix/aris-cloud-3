# Day 7 — Plan Hotfix para cierre de gate v1.0.2

Fecha: 2026-02-14
Estrategia: mantener RC + cerrar bloqueadores de publicación estable.

## Checkpoint Δ1 — Branch y ownership
- Δ Hotfix branch: `hotfix/v1.0.2-release-gate`.
- Δ Owner release engineering: Operaciones + QA release.
- Δ Alcance: **solo pipeline/operación de release** (sin cambios de endpoints/payloads/reglas backend).

## Checkpoint Δ2 — Plan de corrección y tiempos
| ID | Acción | Responsable | ETA máxima | Salida esperada |
|---|---|---|---|---|
| HF-01 | Ejecutar build oficial en runner Windows | Release Eng | T+2h | `dist/ARIS_CONTROL_2.exe` generado |
| HF-02 | Calcular y registrar SHA256 | Release Eng | T+2h 15m | `ARIS_CONTROL_2.exe.sha256` |
| HF-03 | Smoke en máquina limpia (abrir/login/tenant-store-user/API) | QA + Operador SUPERADMIN | T+4h | Reporte T+0 con PASS/FAIL por paso |
| HF-04 | Re-ejecutar rollback drill real con binario previo | Ops | T+6h | Acta rollback <15 min |
| HF-05 | Reunión de re-gate GO/NO-GO | PM + QA + Ops | T+6h 30m | Decisión final firmada |

## Checkpoint Δ3 — Criterio de salida de hotfix
Para pasar de NO-GO a GO deben cumplirse simultáneamente:
1. `.exe` estable generado y verificable en Windows.
2. SHA256 publicado y validado contra asset descargado.
3. Smoke T+0 en limpio con todos los pasos en PASS.
4. Rollback drill real ejecutado en tiempo objetivo.
