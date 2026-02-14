# Day 7 — Smoke T+0 v1.0.5

Fecha: 2026-02-14  
Estado global: **FAIL/BLOCKED por precondición de release estable**

## Checkpoint Δ1 — Precondiciones
- Δ Release estable `v1.0.5` publicada: **NO** (NO-GO activo).
- Δ Asset `ARIS_CONTROL_2.exe` en release estable: **NO**.
- Δ SHA256 oficial verificable de release estable: **NO**.

## Checkpoint Δ2 — Matriz de pasos T+0
| Paso requerido | Estado | Evidencia |
|---|---|---|
| Verificar asset publicado + hash | FAIL | No existe release estable `v1.0.5` |
| a) Abrir `.exe` en máquina limpia | FAIL | Bloqueado por ausencia de asset estable |
| b) Login OK | FAIL | Depende de ejecución del `.exe` estable |
| c) Flujo base Tenant/Store/User según permisos | FAIL | Depende de login sobre app estable |
| d) Conectividad API al endpoint base | BLOCKED | Sin app estable; intento directo de red desde este entorno con `curl` falló por túnel/proxy 403 |

## Checkpoint Δ3 — Conclusión
- Δ Smoke T+0 no certificable en Day 7 v1.0.5 por bloqueo crítico de publicación.
- Δ Queda condicionado a HF-01..HF-07 del plan hotfix.
