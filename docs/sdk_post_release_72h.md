# SDK Post-release Observability (72h)

## Objetivo
Monitorear estabilidad operativa del SDK en una ventana de 72h post-release, consolidar evidencia y documentar incidentes/fixes sin romper contratos de configuración ni comportamiento de caché.

## Ventana de observación
- **T+0 (release + validación inicial)**
  - Verificar pipeline principal de SDK en verde.
  - Ejecutar smoke manual post-release.
  - Confirmar `load_config` estricto (sin fallback runtime para `ARIS3_API_BASE_URL`).
- **T+24 (primer ciclo productivo)**
  - Revisar pass rate de CI acumulado.
  - Revisar errores de red y primeros timeouts de polling.
  - Confirmar ausencia de incidentes por cache stale en exports polling.
- **T+48 (estabilidad intermedia)**
  - Medir tendencia de flaky tests y repetir smoke.
  - Validar guardrails de caché por-request (`use_get_cache=False`) en tests.
- **T+72 (cierre de estabilización)**
  - Consolidar métricas finales.
  - Cerrar/actualizar incidentes.
  - Publicar backlog priorizado v1.1.1.

## Métricas de seguimiento
| Métrica | Definición | Fuente | Umbral objetivo | Estado 72h |
|---|---|---|---|---|
| Pass rate CI | % de jobs exitosos del SDK | GitHub Actions (`clients-python-sdk` + smoke post-release) | >= 95% | Pendiente consolidar en ejecución real |
| Flaky tests | Tests que alternan pass/fail sin cambios | Historial de re-runs en CI | 0 críticos / <=2 no críticos | Pendiente consolidar en ejecución real |
| Errores de red | Fallas de transporte (`TransportError`) por ejecución | Logs tests/smoke | Tendencia decreciente, sin bloqueantes | Pendiente consolidar en ejecución real |
| Timeouts de polling | `TimeoutError` en `wait_for_export_ready` | Tests de exports + smoke | 0 inesperados | Pendiente consolidar en ejecución real |
| Cache stale incidente | Casos donde polling lee estado obsoleto por caché | Tests de exports/caché + incidentes | 0 | Pendiente consolidar en ejecución real |

## Evidencia operativa capturada
- Smoke automation dedicado para validar config estricta, flujo `CREATED -> READY` y caché GET fuera de polling.
- Workflow manual (`workflow_dispatch`) para ejecutar smoke y publicar artifact JSON/log.
- Tests de no-regresión para garantizar que `wait_for_export_ready` no altera estado global de `enable_get_cache` y que `use_get_cache=False` no lee/escribe caché.

## Tabla de incidentes (72h)
> Actualizar durante la ventana operativa. Si no hay incidentes, mantener “Sin incidentes”.

| Fecha (UTC) | Impacto | Causa raíz | Fix aplicado | Estado |
|---|---|---|---|---|
| Sin incidentes | N/A | N/A | N/A | Cerrado |
