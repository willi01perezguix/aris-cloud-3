# Release Notes — ARIS3 0.1.0-rc.1

## Resumen
- Paquete RC Sprint 4 Día 7 con evidencia operativa y checklist de go-live/rollback.
- Scripts operativos para UAT, test matrix, performance smoke, security gate y export OpenAPI.

## Cambios relevantes
- Version bump a `0.1.0-rc.1`.
- Generación de artifacts en `artifacts/release_candidate/`.
- Documentación actualizada para UAT, seguridad, idempotencia y recovery.

## Requisitos antes de GO
- Ejecutar UAT en ambiente final.
- Completar test matrix sqlite/postgres sin interrupciones.
- Ejecutar integrity scan y backup/restore drill con DB poblada.
