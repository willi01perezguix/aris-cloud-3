# Backlog v1.0.3 — Top 10 priorizado (Day 1 kickoff)

Criterio: priorización por **impacto + riesgo + esfuerzo** manteniendo contrato API/endpoints sin cambios.

| Prioridad | ID | Item | Impacto | Riesgo | Esfuerzo | Estado Day 1 |
|---:|---|---|---|---|---|---|
| 1 | QW1 | UX operativa: unificar error visible `code + message + trace_id` en Stores/Users/Actions | Alto | Bajo | Bajo | ✅ Implementado |
| 2 | QW2 | Productividad UI admin: refresh explícito + loading claro preservando tenant/filtros | Alto | Bajo | Bajo | ✅ Implementado |
| 3 | QW3 | Shortcut de paginación rápida (`first/last`) en listados admin | Medio | Bajo | Bajo | Pendiente |
| 4 | QW4 | Copia de ayuda contextual para errores 401/403/422 en consola | Medio | Bajo | Bajo | Pendiente |
| 5 | QW5 | Normalizar mensajes empty-state con siguiente acción recomendada | Medio | Bajo | Bajo | Pendiente |
| 6 | BL6 | Señal de latencia por llamada (ms) en listados admin | Alto | Medio | Medio | Pendiente |
| 7 | BL7 | Export CSV con nombre determinístico (tenant+timestamp) | Medio | Bajo | Medio | Pendiente |
| 8 | BL8 | Check de sesión expirada previo a mutaciones sensibles | Alto | Medio | Medio | Pendiente |
| 9 | BL9 | Runbook smoke automatizado post-release v1.0.3 | Alto | Medio | Medio | Pendiente |
| 10 | BL10 | Telemetría de errores de operador (agregado por código) | Medio | Medio | Medio | Pendiente |

## Quick wins seleccionados hoy
- **QW1** y **QW2** por mejor relación impacto/riesgo/esfuerzo y rollback inmediato por revert de commit.
