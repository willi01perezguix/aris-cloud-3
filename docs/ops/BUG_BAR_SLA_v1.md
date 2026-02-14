# ARIS_CONTROL_2 — Bug Bar + SLA Operativo v1

## Estado
- **Aplicación:** `PREPARADO / PENDIENTE ACTIVACIÓN`
- **Dependencia:** Levantar gate inicial Prompt 15.

| Severidad | Impacto | Tiempo objetivo de respuesta | Tiempo objetivo de mitigación | Canal de escalación | Responsable por rol |
|---|---|---:|---:|---|---|
| SEV1 | Servicio crítico caído, pérdida de operación principal (login o contexto tenant) | 15 min | 4 h (mitigación), 24 h (correctivo inicial) | Incidente mayor + war room | Incident Commander + Tech Lead + Backend Owner |
| SEV2 | Degradación alta en flujo crítico con workaround limitado | 30 min | 8 h (mitigación), 48 h (correctivo) | Canal incidentes + on-call | Tech Lead + QA Lead + Owner de módulo |
| SEV3 | Falla funcional no crítica con impacto moderado | 4 h | 3 días hábiles | Canal mantenimiento semanal | Owner de módulo + QA |
| SEV4 | Defecto menor/cosmético/documentación | 1 día hábil | Próximo ciclo planificado | Backlog regular | Product/Ops coordinator |

## Reglas operativas
1. Toda incidencia debe incluir severidad, alcance tenant/store/user y evidencia mínima.
2. Cualquier incidencia SEV1/SEV2 requiere actualización de estado cada 60 minutos.
3. Cierre de incidencia exige validación QA de no regresión en flujo afectado.
4. Incidencias sin owner asignado no pasan triage.
