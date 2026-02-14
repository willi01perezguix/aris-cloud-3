# INCIDENT_ROLLBACK_RUNBOOK_v1

## Estado
- Documento listo para uso operativo.
- Aplicable a producción una vez levantado el bloqueo de release del gate inicial.

## Matriz de severidad

| Severidad | Definición | Tiempo objetivo de respuesta | Contención inicial |
|---|---|---|---|
| SEV1 | Caída total, crash UI generalizado o corrupción de flujo tenant->store->user | <= 10 minutos | Congelar cambios, war room, mitigación inmediata y evaluación de rollback |
| SEV2 | Degradación parcial de login o módulos críticos con workaround | <= 30 minutos | Limitar impacto, activar feature guardrails, monitoreo reforzado |
| SEV3 | Incidencia menor sin impacto crítico de negocio | <= 4 horas | Registrar, priorizar fix en backlog inmediato |

## Pasos de contención
1. Clasificar incidente (SEV1/2/3) y asignar Incident Commander.
2. Confirmar alcance: tenants afectados, stores afectados, usuarios afectados.
3. Aplicar mitigación no disruptiva (reinicio controlado, aislamiento de tráfico, restricción temporal).
4. Si la mitigación no estabiliza dentro del SLO de respuesta, pasar a rollback.
5. Documentar cronología minuto a minuto.

## Criterio de rollback
Ejecutar rollback cuando ocurra cualquiera de estas condiciones:
- SEV1 activo > 15 minutos sin mitigación efectiva.
- Inconsistencia tenant->store->user reproducible y sin fix seguro inmediato.
- Error crítico persistente en login o conectividad API base con impacto transversal.

## Checklist de comunicación interna
- [ ] Aviso inicial en canal de incidentes con severidad y alcance.
- [ ] Actualización cada 15 minutos (SEV1) / 30 minutos (SEV2).
- [ ] Notificación de decisión de rollback (si aplica) y ETA.
- [ ] Confirmación de recuperación y estado estable.
- [ ] Postmortem preliminar compartido <= 24h.

## Evidencia mínima post-incidente
- Timeline del incidente (detección, contención, resolución).
- Logs/comandos clave usados para diagnóstico.
- Resultado de smoke posterior a mitigación/rollback.
- Impacto final cuantificado (duración, usuarios/tenants afectados).
- Acciones preventivas y owner con fecha compromiso.
