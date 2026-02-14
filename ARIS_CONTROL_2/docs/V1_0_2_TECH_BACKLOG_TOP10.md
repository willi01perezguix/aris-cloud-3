# ARIS_CONTROL_2 — Backlog Técnico v1.0.2 (Top 10)

Fecha: 2026-02-14  
Objetivo: priorizar mejoras incrementales, rollback fácil y sin cambios de contrato API.

| Prioridad | Ítem | Impacto | Riesgo | Esfuerzo | Notas |
|---|---|---:|---:|---:|---|
| 1 | UX: mensajes de error operativos con diagnóstico accionable | Alto | Bajo | Bajo | Quick win Day 1 |
| 2 | Operación: chequeo visible de conectividad API + health/ready | Alto | Bajo | Bajo | Quick win Day 1 |
| 3 | Estados vacíos/carga homogéneos en listados | Alto | Bajo | Bajo | Quick win Day 1 |
| 4 | Hardening de retry/backoff en cliente HTTP (sin cambiar contratos) | Alto | Medio | Medio | Mantener idempotencia |
| 5 | Métricas de latencia por operación en cliente desktop | Medio | Bajo | Medio | Trazabilidad operativa |
| 6 | Auditoría UX: incluir trace_id en rutas de error visibles | Medio | Bajo | Bajo | Soporte/forense |
| 7 | Guías de recuperación rápida ante pérdida de conectividad | Medio | Bajo | Bajo | Runbook operacional |
| 8 | Validación de filtros UI con hints contextuales | Medio | Bajo | Bajo | Evita consultas vacías |
| 9 | Smoke extendido post-login Tenant/Store/User | Alto | Bajo | Medio | Protección de flujo crítico |
| 10 | Reporte interno de estabilidad v1.0.2-dev diario | Medio | Bajo | Bajo | Seguimiento de riesgos |

## Criterio de priorización
- **Impacto** sobre operación diaria de administración Tenant/Store/User.
- **Riesgo** de regresión contra estabilidad v1.0.1.
- **Esfuerzo** para entregar PR pequeño y rollback inmediato.
