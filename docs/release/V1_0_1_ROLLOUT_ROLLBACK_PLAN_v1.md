# ARIS_CONTROL_2 — Plan de Rollout y Rollback v1.0.1

## Estado
- **Estado actual:** `PREPARADO (NO EJECUTABLE HASTA GATE GO)`

## 1) Prerrequisitos de release
1. Gate Prompt 15 en GO.
2. Smoke post-release previo sin críticos abiertos.
3. Hash SHA256 del `.exe` publicado y verificable.
4. Bug Bar/SLA vigente con responsables on-call asignados.

## 2) Secuencia de publicación (rollout)
1. Congelar rama release v1.0.1 y etiquetar build candidata.
2. Ejecutar matriz mínima de pruebas obligatorias.
3. Publicar artefactos y notas de release internas.
4. Habilitar monitoreo intensivo T+0.
5. Confirmar operación estable en T+2h y T+24h.

## 3) Verificación post-publicación
- **T+0:** Login/sesión, tenant context, endpoint default, errores controlados.
- **T+2h:** Revisión de incidentes SEV1/SEV2 y salud de módulos críticos.
- **T+24h:** Confirmación de estabilidad sostenida + cierre de ventana de observación.

## 4) Umbrales de rollback
- 1 incidente SEV1 sin mitigación en 30 min.
- 2+ incidentes SEV2 simultáneos en flujo crítico.
- Error sistemático en login o fuga de contexto tenant.

## 5) Pasos exactos de rollback
1. Declarar evento rollback y congelar despliegues nuevos.
2. Restaurar versión estable previa aprobada.
3. Validar smoke mínimo post-rollback.
4. Comunicar estado y ETA de corrección.
5. Abrir postmortem con causa raíz y acciones.

## 6) Comunicación interna
- Canal incidente principal + resumen ejecutivo cada 60 min durante evento.
- Cierre: reporte final con impacto, causa y plan preventivo.
