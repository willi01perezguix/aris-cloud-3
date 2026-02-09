# Sprint 3 Day 3 - Stock Actions (ARIS 3)

## Endpoint

`POST /aris3/stock/actions`

### Required headers
- `Authorization: Bearer <token>`
- `Idempotency-Key: <key>`

### Required fields
- `transaction_id`
- `action`
- `payload` (action-specific)

### Notes
- Actions enforce tenant scope and `STORE_MANAGE` permission checks.
- EPCs must be 24-character uppercase hex when supplied.
- EPC lifecycle actions move RFID items back to `PENDING` with `epc=None`.
- Write-off actions remove stock rows and allow `LOST` only outside `IN_TRANSIT`.

### Supported actions
- `WRITE_OFF`
- `REPRICE`
- `MARKDOWN_BY_AGE`
- `REPRINT_LABEL`
- `REPLACE_EPC`
- `MARK_EPC_DAMAGED`
- `RETIRE_EPC`
- `RETURN_EPC_TO_POOL`
