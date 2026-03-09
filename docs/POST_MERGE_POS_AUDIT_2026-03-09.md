# Post-merge POS/Checkout/Release Gate audit (main state)

## Verdict
- POS runtime for checkout/cash precondition and PAID status is aligned.
- Action contract currently supports canonical uppercase and lowercase aliases.
- REFUND_ITEMS and EXCHANGE_ITEMS remain implemented in runtime+schema+OpenAPI.
- One documentation artifact (`docs/api-prune-report.md`) is inconsistent with the current runtime/schema.
- Release gate script avoids heavy imports at module load, forces sqlite in matrix check, and explicitly runs both critical smoke suites.

## Key evidence
- Router action normalization: `action = str(payload.action).upper()`.
- Checkout marks sales as `PAID`.
- CASH without open session returns business conflict via `_require_open_cash_session`.
- Action union includes CHECKOUT/CANCEL/REFUND_ITEMS/EXCHANGE_ITEMS plus lowercase aliases.
- Smoke tests validate CASH precondition and successful PAID checkout.
