# SDK Backlog v1.1.1 — Top 10 Priorizado

| # | Item | Impacto | Esfuerzo | Prioridad | Criterio de aceptación |
|---|---|---|---|---|---|
| 1 | Telemetría de polling por estado (`CREATED`, `READY`, `FAILED`) | Alta visibilidad operativa de exports | M | P0 | Se emiten eventos con estado inicial/final y latencia, validados por tests unitarios. |
| 2 | Retries con jitter configurable para requests idempotentes | Reduce picos por retry sincronizado | M | P0 | Config permite jitter on/off y rango; tests validan backoff no determinístico dentro de límites. |
| 3 | CLI utilitaria para smoke SDK (config + exports + cache) | Facilita validación post-release por soporte | S | P0 | Comando ejecuta checks y retorna exit code 0/1 con artifact JSON. |
| 4 | Dashboard de health del SDK (CI pass, flaky, red, timeouts) | Vista única de estabilidad release-to-release | M | P1 | Documento/runbook define métricas y fuente automatizada en artifact consolidado. |
| 5 | Hardening de errores de red transitorios (mensajes accionables) | Disminuye MTTR para incidentes de conectividad | S | P1 | `TransportError` incluye clasificación y recomendación breve; tests verifican payload de error. |
| 6 | Contrato de cache por endpoint documentado | Evita regresiones de stale cache | S | P1 | Tabla por endpoint con policy cache/no-cache; tests alineados para endpoints críticos. |
| 7 | Test matrix con seeds para detección de flakes | Reduce ruido en CI y retrabajo | M | P1 | Pipeline nightly ejecuta N repeticiones y reporta tests inestables automáticamente. |
| 8 | Timeout adaptativo para `wait_for_export_ready` por tipo de export | Mejor experiencia para exports largos | M | P2 | API de cliente acepta perfil de timeout y mantiene compatibilidad backward. |
| 9 | Ejemplos de integración observabilidad (logs/trace-id) | Acelera adopción por equipos consumidores | S | P2 | README incluye snippet y salida esperada con `trace_id`. |
| 10 | Validación estática de env obligatorias en preflight | Previene fallos tardíos de configuración | S | P2 | Preflight falla temprano cuando falta `ARIS3_API_BASE_URL` y guía remediación. |
