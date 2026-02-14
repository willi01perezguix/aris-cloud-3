# MONITORING_72H_PLAN_v1

## Estado de activación
- **Estado actual:** `NO-GO` (plan no activado en producción por gate inicial fallido de Prompt 14).
- **Activación:** inmediata cuando se cumplan los 3 prerequisitos del gate (release estable + `.exe` con checksum + Prompt 13 en GO).
- **Endpoint por defecto a validar:** `https://aris-cloud-3-api-pecul.ondigitalocean.app/`

## Ventanas operativas (plan ejecutable)

| Ventana | Qué validar | Umbral de alerta | Acción inmediata si falla | Responsable |
|---|---|---|---|---|
| T+0 | Health API, login, selección tenant, listado stores/users por tenant, errores UI visibles | Cualquier 5xx en health/login, crash UI, inconsistencia tenant->store->user | Declarar incidente SEV1, congelar cambios, iniciar runbook de rollback | Incident Commander (On-call Ops) |
| T+2h | Repetición smoke crítico + latencia percibida | p95 login o listados > 2.5s por 10 min | Escalar a Backend Lead, habilitar mitigación operativa, evaluar rollback | On-call Backend |
| T+6h | Tendencia de errores UI/API y consistencia multi-tenant | >1% errores en flujos críticos por 15 min | Contención + triage SEV2, bloquear nuevas promociones | SRE / Ops |
| T+24h | Estabilidad diaria, auditoría de sesión/autenticación | Reautenticación anómala >3% o fallas de login repetidas | Rotar credenciales/sesiones afectadas, abrir incidente formal | Security + Ops |
| T+48h | Revalidación integral smoke + drift funcional | Cualquier regresión funcional tenant/store/user | Ejecutar rollback si no hay mitigación en <30 min | Incident Commander + Product |
| T+72h | Cierre hiper-care, revisión de incidentes abiertos | Incidentes críticos abiertos >0 | Extender hiper-care 24h y mantener guardia reforzada | Ops Manager |

## Checklist operativo por ventana
1. Confirmar conectividad al endpoint por defecto.
2. Validar login y flujo tenant context completo.
3. Revisar errores de cliente/API y severidad.
4. Registrar evidencia (timestamp, comando/log, resultado PASS/FAIL).
5. Decidir continuidad o escalamiento según umbrales.

## Evidencia mínima por checkpoint
- Captura de resultado de health/check o prueba equivalente.
- Resultado smoke resumido PASS/FAIL.
- Métrica de latencia percibida (p50/p95 si está disponible).
- Decisión operativa (continuar / escalar / rollback).
