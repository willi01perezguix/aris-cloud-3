# BACKLOG_POST_RELEASE_TOP10_v1

Prioridad inmediata para habilitar GO operativo post-release.

| # | Item | Impacto | Esfuerzo | Prioridad |
|---|---|---|---|---|
| 1 | Promover release estable `v1.0.0` (o versión final oficial) | Alto | Medio | P0 |
| 2 | Publicar `ARIS_CONTROL_2.exe` oficial y documentar SHA256 | Alto | Bajo | P0 |
| 3 | Cerrar bloqueantes de Prompt 13 y actualizar estado a GO | Alto | Medio | P0 |
| 4 | Ejecutar smoke post-release T+0 con evidencia completa | Alto | Bajo | P0 |
| 5 | Automatizar registro PASS/FAIL por checkpoint 72h | Medio | Medio | P1 |
| 6 | Definir dashboard único de salud login + tenant/store/user | Medio | Medio | P1 |
| 7 | Estandarizar plantilla de incidente + postmortem 24h | Medio | Bajo | P1 |
| 8 | Endurecer validación de artefactos release en CI (checksum gate) | Medio | Medio | P1 |
| 9 | Ejecutar simulacro de rollback en ventana controlada | Medio | Medio | P2 |
| 10 | Revisar deuda documental duplicada entre `docs/` y `runbooks/` | Bajo | Bajo | P2 |

## Criterio de priorización
- **Impacto:** riesgo operativo y bloqueo directo de GO.
- **Esfuerzo:** complejidad de ejecución en ciclo corto (24-72h).
