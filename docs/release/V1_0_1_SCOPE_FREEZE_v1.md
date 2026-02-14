# ARIS_CONTROL_2 — Scope Freeze v1.0.1

## Estado
- **Freeze:** `DEFINIDO (operación bloqueada por gate NO-GO)`
- **Principio:** Prioridad absoluta a estabilidad, trazabilidad, UX crítica y robustez operativa.

## IN v1.0.1 (priorizado)
| ID | Ítem | Criterio de aceptación | Riesgo | Dependencia |
|---|---|---|---|---|
| IN-01 | Corrección de manejo de error en login sin crash | Error autenticación muestra feedback y mantiene app estable | Medio | API auth estable |
| IN-02 | Endurecer renovación/expiración de sesión | Sesión expirada redirige/controla estado sin fuga | Medio | Gestión de token |
| IN-03 | Validación estricta de contexto tenant->store->user | No hay mezcla de datos entre tenants | Alto | Filtros backend existentes |
| IN-04 | Mejorar mensajes de error API (timeouts/5xx) | Mensaje claro + opción de reintento | Bajo | Cliente UI |
| IN-05 | Smoke automatizable post-release T+0 | Script/flujo ejecutable con evidencia real | Medio | Runbook smoke |
| IN-06 | Checklist release con hash SHA256 obligatorio | No release sin hash publicado | Bajo | Pipeline release |
| IN-07 | Registro de incidentes y dueños en handoff | 100% incidentes con owner y ETA | Bajo | Proceso ops |
| IN-08 | Ajustes UX críticos en Tenants/Stores/Users | Flujos críticos sin bloqueos de navegación | Medio | QA funcional |
| IN-09 | Prueba de conectividad endpoint por defecto obligatoria | Validación explícita contra endpoint oficial | Bajo | Config app |
| IN-10 | Verificación de arranque `.exe` en smoke oficial | Arranque exitoso documentado | Alto | Entorno Windows |

## OUT v1.0.1 (pospuestos)
| ID | Ítem pospuesto | Motivo de exclusión |
|---|---|---|
| OUT-01 | Nuevos módulos funcionales de negocio | Fuera de objetivo de estabilización |
| OUT-02 | Refactor arquitectónico amplio UI/API | Riesgo alto para ventana corta |
| OUT-03 | Cambios de contrato API | Restringido por lineamiento del release |
| OUT-04 | Reemplazo total de framework de build cliente | Alto costo y baja prioridad inmediata |
| OUT-05 | Integraciones externas no críticas | No impactan estabilidad core |
