# ARIS-CORE-3 App Shell (Sprint 7 Day 3/4)

## Purpose
This app-track deliverable establishes the ARIS-CORE-3 desktop shell foundation for:
- authentication bootstrap,
- `/aris3/me` profile loading,
- effective-permissions UI gating (default deny, deny-over-allow),
- navigation placeholders for upcoming module integrations.

Sprint 7 Day 4 adds Stock module integration for full-table query, EPC/SKU imports, and SKU→EPC migration flows.

No contract-breaking API changes are introduced.

## Run
From repository root:

```bash
export ARIS3_API_BASE_URL="https://api.example.com"
python clients/python/apps/core_app/main.py
```

## Environment configuration
Core inputs:
- `ARIS3_API_BASE_URL` (required, or `ARIS3_API_BASE_URL_<ENV>`)
- `ARIS3_ENV` (`dev`/`staging`/`prod`, default `dev`)
- `ARIS3_CONNECT_TIMEOUT_SECONDS` (optional)
- `ARIS3_READ_TIMEOUT_SECONDS` (optional)
- `ARIS3_APP_ID` (optional)
- `ARIS3_DEVICE_ID` (optional)

`.env` is supported via `python-dotenv`.

## Auth flow (text diagram)
1. App bootstrap starts.
2. Existing session token present?
   - No: route `login`.
   - Yes: load profile (`/aris3/me`).
3. After login success: establish session, load profile.
4. If profile has `must_change_password=true`: route `change_password`.
5. Load effective permissions.
6. Build permission gate and open shell.
7. Logout clears persisted session and routes back to login.

## Permission gating behavior
- Default deny when permission key is absent.
- Deny overrides allow if conflicting entries are present.
- Menu modules rendered only when any required key is allowed.
- Stock write actions (import EPC, import SKU, migrate SKU→EPC) are hidden/disabled unless matching write permissions are granted.

## Stock module (Sprint 7 Day 4)

### Stock list usage
- Use `StockListView.load(filters)` to query official stock full-table (`GET /aris3/stock`) via hardened SDK.
- Response is rendered as:
  - `meta` (pagination/sort),
  - `table` (`rows` in full-column-friendly model),
  - `totals` (`RFID`, `PENDING`, `TOTAL`, plus raw totals payload).
- Includes explicit loading/error/empty-state flags and trace metadata pass-through when present.

### Filters + pagination/sort behavior
- Supported minimum filters: `q`, `description`, `var1_value`, `var2_value`, `sku`, `epc`, `location_code`, `pool`.
- Also supports `page`, `page_size`, `sort_by`, and `sort_dir`.
- `StockFiltersPanel.as_query()` strips `None`/empty values before service call.

### Import EPC steps
1. Build multi-line payload (`lines`) with full line block.
2. Each line must satisfy:
   - `epc` = 24 HEX,
   - `qty` = `1`,
   - `status` = `RFID`.
3. Submit via `ImportEpcView.submit(lines)`.
4. Service injects `transaction_id` + `idempotency_key`.
5. Result returns per-line outcomes + trace/idempotency refs and refreshes stock list.

### Import SKU steps
1. Build multi-line payload (`lines`) with full line block (`epc` empty/null).
2. Validate:
   - required fields present,
   - `qty > 0`,
   - `status = PENDING`.
3. Submit via `ImportSkuView.submit(lines)`.
4. Service injects idempotency metadata and returns per-line results.
5. Stock list/totals refresh on success.

### Migrate SKU→EPC steps
1. Build migration payload with destination `epc` and source data block context.
2. Enforce destination EPC format (24 HEX) and pending-status precondition.
3. Submit via `MigrateSkuToEpcView.submit(payload)`.
4. Service includes `transaction_id` + `idempotency_key`.
5. UI declares expected effect explicitly: `PENDING -1, RFID +1, TOTAL unchanged`.
6. Stock list/totals refresh after success.

### Permission requirements
- Stock list: requires one of `stock.view` / `STORE_VIEW`.
- Import EPC: requires one of `stock.import_epc` / `stock.write` / `STORE_WRITE`.
- Import SKU: requires one of `stock.import_sku` / `stock.write` / `STORE_WRITE`.
- Migrate SKU→EPC: requires one of `stock.migrate_sku_to_epc` / `stock.write` / `STORE_WRITE`.

### Known limitations
- Module is represented as view-model/state classes (not yet bound to a GUI toolkit).
- Permission aliases may vary by tenant policy templates; the gate remains default-deny.
- Server-side uniqueness and tenant rules are enforced by backend contracts and surfaced via mapped errors.
