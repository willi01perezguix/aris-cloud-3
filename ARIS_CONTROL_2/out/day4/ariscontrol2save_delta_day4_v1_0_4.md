# ariscontrol2save (delta-only) — v1.0.4 Day 4

## Cambios aplicados
- Tabla avanzada en listados `tenants/stores/users`:
  - Ordenamiento por columna (`asc/desc`) persistido por módulo.
  - Configuración de columnas visibles persistida por módulo.
  - Restablecer vista al estado por defecto.
- Exportación CSV de vista actual:
  - Exporta únicamente filas visibles/filtradas de la vista activa.
  - Incluye metadatos de operación en cabecera (`timestamp_local`, `module`, `tenant_id`, `filters`).
  - Sanitiza campos sensibles (`token`, `secret`, `password`, etc.).
- Consistencia operacional:
  - Respeta contexto tenant y filtros/paginación al exportar y al volver.
  - Opción de exportación solo visible cuando hay permiso de lectura inferido.
- Integridad visual/datos:
  - Normalización de valores vacíos a `—`.
  - Formato consistente de estados y fecha/hora.
  - Nombres de columnas estables entre tabla y CSV.

## Riesgos
- El ordenamiento se aplica sobre filas de la página actual (no reordena en backend).
- La visibilidad de exportación usa `effective_permissions` si existe; en sesiones sin esa lista, cae a rol autenticado.

## Rollback simple
1. Revertir commit Day 4 en rama actual.
2. Validar smoke: listados básicos + export CSV legacy + persistencia de filtros/paginación.
3. Eliminar contexto local (`~/.aris_control_2_operator_context.json`) si se requiere limpieza de estado de vista.
