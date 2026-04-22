# Reports Profit Backend Verification (2026-04-22)

Scope reviewed:
- app/aris3/services/reports.py
- app/aris3/routers/pos_sales.py
- tests/test_reports_profit_cogs_backend.py
- tests/test_reports_day3_profit_snapshot_integrity.py

## Confirmations

1. Profit is not equal to net sales by default; it subtracts COGS.
2. Formula implemented in report rows:
   - `net_cogs = cogs_gross - cogs_reversed_from_returns`
   - `net_profit = net_sales - net_cogs`
3. Sale-line `cost_price_snapshot` is used first when present.
4. POS checkout writes `cost_price_snapshot` for EPC and SKU lines when missing.
5. Store isolation remains enforced in sales/returns queries and stock fallback lookups by `store_id`.
6. Finalized sale statuses counted case-insensitively: `PAID`, `COMPLETED`, `CLOSED`, `FINALIZED` via `func.upper(...)`.
7. Draft/canceled sales are excluded since only reportable finalized statuses are included.
8. Coverage passing includes:
   - one-line profit,
   - quantity > 1,
   - multi-line profit,
   - store isolation,
   - missing cost fallback,
   - Guatemala same-day range (timezone=`America/Guatemala`).

## Old sales fallback support

Yes. If sale-line rows are missing for a sale, sales revenue falls back to `PosSale.total_due` for that sale.

## Current limitation

When no deterministic cost source exists (snapshot/item_uid/epc/sku-variant), line cost is treated as `0.00` and tracked in diagnostics (`missing_cost_lines`, `missing_cost_total_qty`).
