# ADR-S4-D7 — Release Candidate, Go-Live y Rollback Drill

## Contexto
Sprint 4 Día 7 exige cierre operativo con UAT final, gates no funcionales, y paquete de release candidate auditable.

## Decisiones
1. Versionado RC usando sufijo `-rc.1` en `pyproject.toml`.
2. Generación de artifacts en `artifacts/release_candidate/` con reportes UAT, test matrix, performance smoke, integrity scan, backup/restore, security gate, y documentación go-live/rollback.
3. Uso de scripts operativos (`scripts/ops/*`) para producir evidencia reproducible.
4. Criterio GO/NO-GO explícito con hard blockers documentados en los reportes.

## Consecuencias
- El RC no se considera aprobado hasta ejecutar UAT en ambiente final.
- Los reportes quedan versionados en artifacts para auditoría.
- Se mantiene la congelación de reglas de negocio y sin features nuevas.

## Estado
Aceptado — Sprint 4 Día 7.
