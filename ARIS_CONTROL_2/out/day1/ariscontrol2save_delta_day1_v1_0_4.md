# ariscontrol2save · delta-only · v1.0.4 Day 1

## Delta funcional
- Se unifica validación visible en formularios críticos de admin con formato `[ERROR] code=... message=... trace_id=...`.
- Se agrega atajo `d` en listados `stores` y `users` para duplicar filtros relacionados (`q`, `status`) sin perder tenant.

## Delta técnico
- `AdminConsole`: helper `_print_validation_error(...)` y `_duplicate_related_filters(...)`.
- Menú de comandos actualizado con `d=duplicar filtros relacionados`.
- Tests unitarios Day 1 ampliados para validar quick wins.

## No-delta (explícito)
- Sin cambios en contrato API.
- Sin cambios de endpoints.
- Endpoint base por defecto intacto.
