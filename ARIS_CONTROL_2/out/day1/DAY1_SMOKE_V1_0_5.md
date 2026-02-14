# Day 1 Smoke Evidence · v1.0.5

## Alcance smoke corto
a) abre app  
b) login OK  
c) startup check muestra estado correcto  
d) tenant persiste al cambiar de módulo  
e) listados responden sin mezcla de tenant

## Evidencia ejecutada en CI local (pytest unit/integration focalizada)
- Cobertura de estado startup y retry UX: `tests/unit/test_main_api_diagnostics.py`.
- Cobertura de atajos admin + persistencia de tenant en navegación/listados: `tests/unit/test_day1_kickoff_quickwins.py`.
- Cobertura previa vigente para login/contexto/tenant-scope: `tests/integration/test_login_me_context.py`, `tests/integration/test_stores_tenant_scope.py`.

## Before / After (captura textual)
- **Before:** conectividad inicial sin acción rápida dedicada y sin etiqueta de estado startup.
- **After:** startup muestra `✅/⚠️/❌` + opción `0` para reintento inmediato, sin bloquear operación.
- **Before:** menú Admin Core orientado por numeración larga.
- **After:** accesos rápidos `t/s/u`, contexto activo visible y mensajes `[loading]`, `[error]`, `[empty]` más explícitos.

> Nota: ARIS_CONTROL_2 es consola interactiva (CLI), por lo que la evidencia visual se documenta como captura textual del flujo.
