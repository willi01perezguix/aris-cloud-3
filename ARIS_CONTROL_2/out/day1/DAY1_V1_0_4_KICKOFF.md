# ARIS_CONTROL_2 · v1.0.4 Day 1 Kickoff

Estado base: post-release v1.0.3 estable.
Versión de trabajo: `v1.0.4-dev`.
Endpoint por defecto: `https://aris-cloud-3-api-pecul.ondigitalocean.app/`.

## Backlog Top 10 (priorizado impacto/riesgo/esfuerzo)

| Pri | Item | Impacto | Riesgo | Esfuerzo | Marca |
|---|---|---|---|---|---|
| 1 | Unificar mensajes de validación en Stores/Users/actions (`code+message+trace_id`) | Alto | Bajo | Bajo | QW1 |
| 2 | Duplicar filtros entre vistas Stores ↔ Users conservando tenant | Alto | Bajo | Bajo | QW2 |
| 3 | Persistir paginación por módulo al navegar/volver | Alto | Bajo | Bajo | QW3 |
| 4 | Retry UX no intrusivo con feedback en listados | Medio | Bajo | Bajo | QW4 |
| 5 | Mejorar mensajes de guardrails tenant/store en altas | Alto | Bajo | Bajo | QW5 |
| 6 | Atajos de navegación rápida entre listados admin | Medio | Bajo | Medio |  |
| 7 | Cobertura unitaria de errores de formulario críticos | Alto | Bajo | Bajo | QW6 |
| 8 | Smoke guiado Day 1 para login/tenant/listados/errores | Alto | Bajo | Bajo | QW7 |
| 9 | Telemetría de contexto visible (tenant/página/filtros) | Medio | Bajo | Medio |  |
| 10 | Limpieza de copy UX en acciones sensibles de users | Medio | Bajo | Medio |  |

## Quick Wins ejecutados hoy

- **QW1**: validaciones de formularios críticos estandarizadas en salida visible (`code`, `message`, `trace_id`) para tenant, tenant/create, store/create, user/create y user/actions.
- **QW2**: nuevo comando para **duplicar filtros** entre Stores y Users, preservando contexto de tenant.

## Riesgos y rollback simple

- Riesgo principal: confusión operativa por nuevo comando `d` en listados.
- Mitigación: comando opcional, sin alterar endpoints ni contratos.
- Rollback simple: revertir commit Day 1 (`git revert <commit>`) y volver al flujo previo.
