# Backlog v1.0.4 — Top 10 priorizado (post Day 7)

Criterio: priorización por **impacto + riesgo + esfuerzo** sin cambios de contrato API/endpoints.

| Prioridad | ID | Item | Impacto | Riesgo | Esfuerzo | Prioridad final |
|---:|---|---|---|---|---|---|
| 1 | B4-01 | Automatizar build y smoke Windows (`.exe`) en runner dedicado | Alto | Alto | Medio | P0 |
| 2 | B4-02 | Publicación automática de SHA256 junto al asset release | Alto | Alto | Bajo | P0 |
| 3 | B4-03 | Pipeline de smoke T+0 en máquina limpia (checklist ejecutable) | Alto | Alto | Medio | P0 |
| 4 | B4-04 | Ejecución periódica de rollback drill real con evidencia <15 min | Alto | Medio | Medio | P1 |
| 5 | B4-05 | Dashboard de errores UI/API con `code/message/trace_id` consolidado | Alto | Medio | Medio | P1 |
| 6 | B4-06 | Reintento controlado para fallos de conectividad endpoint default | Medio | Medio | Bajo | P1 |
| 7 | B4-07 | Plantilla de release notes estable + riesgos + rollback resumido | Medio | Bajo | Bajo | P1 |
| 8 | B4-08 | Alertas automáticas para incumplimiento checkpoints 72h | Medio | Medio | Bajo | P2 |
| 9 | B4-09 | Reporte comparativo RC vs estable (asset/hash/smoke) | Medio | Bajo | Bajo | P2 |
| 10 | B4-10 | Kit de evidencia one-click para comité GO/NO-GO | Medio | Bajo | Medio | P2 |

## Nota de continuidad
- Este backlog se activa inmediatamente después del cierre de hotfix Day 7 y previo al próximo intento de publicación estable.
