# ADR-S4-D6: Operability Hardening (Observabilidad + Integridad + Drill)

## Contexto
Se requiere fortalecer la operación en producción sin romper contrato:
- Logging estructurado.
- Métricas internas.
- Scanner de invariantes (CLI).
- Backup/restore drill auditable.

## Decisiones
1. **Logging estructurado** con middleware de observabilidad, sin incluir secretos.
2. **Métricas Prometheus** usando `prometheus-client` y endpoint interno `/aris3/ops/metrics` protegido por feature flag `METRICS_ENABLED`.
3. **Integrity Scanner** como CLI `python -m app.ops.integrity_scan` sin endpoints públicos nuevos.
4. **Backup/Restore Drill** basado en export JSONL por tablas core, manifest con checksums y restore verify en base temporal SQLite.

## Tradeoffs
- El restore verify usa SQLite temporal en vez de un schema PostgreSQL dedicado para simplificar ejecución en CI.
- El backup lógico JSONL no sustituye `pg_dump` para recuperación total; sirve como drill operativo validable.

## Riesgos
- Escalamiento de volumen: export JSONL puede ser pesado en bases grandes.
- Diferencias entre tipos PostgreSQL/SQLite podrían afectar restore verify.

## Mitigaciones
- Timeout configurable (`OPS_DRILL_TIMEOUT_SEC`).
- Uso de manifest y checksums para integridad.
- Plan de rollback en runbook y reporte auditable.

