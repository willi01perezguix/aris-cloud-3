# Plan y Resultados UAT — ARIS3 (Sprint 4 Día 7)

## Objetivo
Validar end-to-end los flujos críticos antes del Release Candidate, respetando las reglas congeladas del sprint.

## Alcance UAT (E2E)
1. Auth/Me
   - login / change-password / me
   - must_change_password
   - scope tenant correcto
2. Stock
   - import-epc (qty=1, EPC 24 HEX único)
   - import-sku (suma PENDING)
   - migrate-sku-to-epc (PENDING-1, RFID+1, total constante)
   - GET /stock full-table con filtros + invariantes de totales
3. Transfers
   - draft -> dispatch -> receive total/parcial
   - report_shortages y resolve_shortages (FOUND_AND_RESEND / LOST_IN_ROUTE MANAGER-only)
   - validaciones: mismo tenant, no auto-traslado, recepción solo destino
4. POS Sales + Cash
   - checkout con CASH/CARD/TRANSFER/mixed
   - reglas de cambio (solo CASH)
   - sesión OPEN obligatoria para CASH
   - cancel / validaciones de estado
5. Refund/Exchange
   - REFUND_ITEMS y EXCHANGE_ITEMS atómicos
   - aplicación de return-policy
   - cash refund => CASH_OUT_REFUND
6. Inventory Counts (Opción A)
   - START/PAUSE/RESUME/CLOSE/CANCEL/RECONCILE
   - bloqueo duro por tienda durante conteo
   - snapshot + diferencias
7. Media
   - resolución VARIANT->SKU->PLACEHOLDER
   - stock devuelve image_* correctamente
8. Admin + RBAC
   - ADMIN ceiling tenant
   - effective-permissions coherente
   - denegaciones auditables

## Ejecución Sprint 4 Día 7
- Script: `python scripts/ops/uat_runner.py`
- Artifacts: `artifacts/release_candidate/uat_report.json` y `artifacts/release_candidate/uat_report.md`

### Resultado
- Estado general: **NOT_EXECUTED** (entorno UAT no disponible en esta ejecución).
- Se debe re-ejecutar en ambiente UAT final previo a Go/No-Go.

## Evidencia
- `artifacts/release_candidate/uat_report.json`
- `artifacts/release_candidate/uat_report.md`
