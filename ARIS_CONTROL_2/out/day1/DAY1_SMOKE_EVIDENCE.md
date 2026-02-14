# Day 1 Smoke & evidencia (v1.0.3-dev)

## Cobertura smoke corta
- [x] Login
- [x] Tenant seleccionado persiste
- [x] Listado stores/users tenant-scoped
- [x] Error API muestra `code + message + trace_id`

## Before/After (delta)
- **Antes**: errores string podían mostrarse sin `code`/`trace_id`.
- **Después**: `ErrorBanner` normaliza salida con `code`, `message` y `trace_id` (o `n/a`).
- **Antes**: refresh en listados admin sin feedback explícito de preservación de contexto.
- **Después**: refresh emite estado `[refresh]` y carga `[loading]` visibles.

## Riesgos
- Riesgo bajo: cambios solo en UX CLI y mensajes.

## Rollback simple
- `git revert <commit_day1_kickoff>`.
