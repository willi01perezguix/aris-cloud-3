# Backlog v1.0.3 — Top 10 priorizado (quick wins primero)

Criterio: mejoras de alta relación impacto/esfuerzo sin romper contratos API.

| Prioridad | Item | Tipo | Impacto | Esfuerzo | Resultado esperado |
|---:|---|---|---|---|---|
| 1 | Pipeline release Windows dedicado con smoke automatizado | Quick win | Alto | Bajo | Evitar bloqueos de packaging |
| 2 | Publicación automática de SHA256 junto al asset | Quick win | Alto | Bajo | Trazabilidad e integridad inmediata |
| 3 | Plantilla única de acta GO/NO-GO + validación checklist | Quick win | Medio | Bajo | Decisión auditada y repetible |
| 4 | Script de verificación T+0 estandarizado | Quick win | Medio | Bajo | Evidencia homogénea por release |
| 5 | Captura estructurada de errores UI/API con trace_id en smoke | Quick win | Medio | Bajo | Mejor diagnóstico de incidentes |
| 6 | Dashboard de estado release gate (semáforos) | Mejora | Medio | Medio | Visibilidad operativa en tiempo real |
| 7 | Prueba de rollback real obligatoria pre-GA | Mejora | Alto | Medio | Reducción de MTTR en incidentes |
| 8 | Paquete de credenciales de prueba controladas para smoke | Mejora | Medio | Medio | Eliminar bloqueos por acceso |
| 9 | Hardening de runbooks de release con tiempos objetivo | Mejora | Medio | Bajo | Ejecución consistente entre turnos |
| 10 | Reporte semanal de salud release (fallas, causas, acciones) | Mejora | Medio | Bajo | Mejora continua de proceso |
