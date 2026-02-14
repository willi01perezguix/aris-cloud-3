# Day 7 — Smoke post-publicación inmediata (T+0)

Fecha: 2026-02-14
Estado global: **BLOCKED (NO-GO activo, sin release estable publicada)**

## Checkpoint Δ1 — Precondición
- Δ Release estable publicada: **NO**.
- Δ Asset descargable `ARIS_CONTROL_2.exe`: **NO**.
- Δ SHA256 publicado: **NO**.

## Checkpoint Δ2 — Matriz T+0
| Paso | Resultado | Evidencia / Nota |
|---|---|---|
| Descargar artefacto publicado | FAIL | No existe release estable v1.0.2 publicada |
| Verificar hash del asset publicado | FAIL | No existe asset publicado para comparar |
| Abrir `.exe` en máquina limpia | FAIL | No hay binario estable liberado |
| Login | FAIL | Depende del paso anterior |
| Flujo Tenant/Store/User por permisos | FAIL | Depende del paso anterior |
| Conectividad API OK | FAIL | Prueba T+0 bloqueada por ausencia de app ejecutable |

## Checkpoint Δ3 — Acción requerida
- Δ Ejecutar `HF-01..HF-05` de `out/day7/DAY7_HOTFIX_PLAN.md` para habilitar nueva corrida T+0.
