# Go-Live Checklist — ARIS3 RC Sprint 4 Día 7

## Preflight
- [ ] Variables de entorno requeridas (DATABASE_URL, OPS_*).
- [ ] Migraciones aplicadas (`alembic upgrade head`).
- [ ] Backup previo confirmado (manifest + checksum).
- [ ] Health/Readiness del entorno destino OK.

## Deploy
- [ ] Desplegar RC (`0.1.0-rc.1`).
- [ ] Verificar `GET /aris3/health` y `GET /aris3/ready`.
- [ ] Validar contratos OpenAPI (artifact `openapi.json`).

## Post-deploy Smoke
- [ ] `GET /aris3/stock` (meta/rows/totals completos).
- [ ] Checkout básico en POS (CASH/CARD).
- [ ] Transferencias (dispatch/receive).
- [ ] Reportes (sales con filtros por fecha).

## Monitoreo 30-60 min
- [ ] Error rate < umbral.
- [ ] p95 latencia estable vs baseline.
- [ ] No CRITICAL en integrity scan.

## Criterios GO / NO-GO
### GO
- UAT y test matrix en verde.
- Backup/restore drill OK.
- Security gate sin FAIL.

### NO-GO (hard blockers)
- CRITICAL en integrity scan.
- Test matrix rojo.
- Backup/restore drill fallido.
- Gate de seguridad FAIL.
