# ariscontrol2save · delta-only · v1.0.5 Day 1

## Delta funcional
- Startup check al iniciar ahora muestra estado explícito: `Conectado`, `Degradado` o `Sin conexión`.
- Se agrega acción rápida `0` para reintentar conectividad sin bloquear el uso de la app.
- Menú Admin Core incorpora accesos rápidos `t/s/u` para Tenants/Stores/Users.
- Se expone contexto activo (tenant/rol) al entrar a Admin Core y se mejora copy de estados `loading/error/empty`.

## Delta técnico
- `main.py`: helper `_print_startup_connectivity_status(...)` + opción `0` en menú principal.
- `admin_console.py`: atajos de navegación y mensajes de estado más claros, manteniendo persistencia de tenant/contexto.
- `diagnostics.py`: versión de trabajo actualizada a `v1.0.5-dev`.
- Tests unitarios ampliados para startup status y accesos rápidos/admin state copy.

## Riesgos + rollback simple
- Riesgo: nuevos atajos (`0`, `t/s/u`) pueden requerir breve adaptación operativa.
- Mitigación: no reemplazan opciones existentes, solo agregan caminos rápidos.
- Rollback simple: `git revert <commit_day1_v1_0_5>`.

## No-delta (explícito)
- Sin cambios de endpoints/payloads ni reglas del backend.
- Endpoint base por defecto se mantiene intacto.
