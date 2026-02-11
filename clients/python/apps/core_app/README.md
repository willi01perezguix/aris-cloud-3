# ARIS-CORE-3 App Shell (Sprint 7 Day 3/4/5)

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

## POS module (Sprint 7 Day 5)

### Sales lifecycle
- `SaleEditorView` supports draft creation, draft loading, line add/edit/remove, draft patch updates, checkout action, and cancel action.
- Draft edits use PATCH-only semantics through `PosSalesService.update_draft(...)`; state transitions are action-based (`checkout`, `cancel`) through `/actions`.
- `SalesListView` loads sales rows and exposes permission-aware checkout/cancel action flags.

### Payment method rules
- Supported methods: `CASH`, `CARD`, `TRANSFER`, and mixed combinations.
- `CARD` requires `authorization_code`.
- `TRANSFER` requires `bank_name` and `voucher_number`.
- `paid_total` must cover `total_due` for checkout; otherwise `missing_amount` is shown and checkout is blocked.
- `change_amount` is only valid against the cash contribution (`CASH` line total).

### CASH checkout precondition
- Any checkout containing `CASH` verifies `PosCashService.current_session()` first.
- Checkout is blocked unless the current session status is `OPEN`.

### POS Cash operations
- `CashSessionView` integrates: current session load, `OPEN`, `CASH_IN`, `CASH_OUT`, and `CLOSE` actions.
- `CashMovementsView` integrates movement history (`GET /aris3/pos/cash/movements`).
- Cash state chip and per-action enable/disable logic prevent invalid state transitions (e.g. no `CASH_IN` when drawer is closed).

### Permission requirements
- POS module visibility: requires one of `pos.sales.view`/`POS_SALE_VIEW` or `pos.cash.view`/`POS_CASH_VIEW`.
- Sales draft write/edit: `pos.sales.write` / `POS_SALE_WRITE`.
- Sales checkout/cancel: `pos.sales.checkout`/`pos.sales.cancel`/`pos.sales.action` aliases (default deny on missing keys).
- Cash operations: `pos.cash.write` / `POS_CASH_WRITE`.

### Known limitations
- Current POS integration is model/view-state oriented (no final UI toolkit binding yet).
- Final cash balancing/day-close flows remain backend-owned and are not redesigned in the core app.
- Action availability assumes canonical backend status values (`OPEN`, `CLOSED`, etc.) and surfaces backend trace/error details when available.

## Sprint 8 Day 2 UX hardening

### UX state model (loading/empty/error/retry)
- Shared state primitives live in `ui/shared/view_state.py` + `ui/shared/state_widgets.py`.
- Standard statuses across key screens: `loading`, `empty`, `success`, `partial_error`, `fatal_error`, `no_permission`.
- Read operations can surface non-blocking retry affordances through `RetryPanel` (flag-gated by `advanced_retry_panel_v1`).
- Stock list can optionally keep the last successful snapshot on read failures when `optimistic_ui_reads_v1` is enabled.

### Validation behavior and operator safeguards
- Shared validators in `ui/shared/validators.py` provide field-level errors and summary banners.
- Enforcement includes:
  - EPC format = 24 HEX,
  - EPC import qty = 1,
  - SKU import qty > 0,
  - payment requirements (`CARD.authorization_code`, `TRANSFER.bank_name + voucher_number`),
  - checkout missing/change display support.
- Mutation flows keep entered values when validation fails and expose explicit `not_applied` markers on failures.
- In-flight actions are guarded (double-submit protection), and destructive actions require explicit confirmation.

### Telemetry / feature-flag usage
- Telemetry uses shared non-PII pipeline (`shared/telemetry`) and is default OFF.
- Core app emits scoped events such as `auth_login_result`, `screen_view`, and call-result/validation/permission signals.
- Feature flags are default-safe OFF and currently gate:
  - `improved_error_presenter_v2`
  - `optimistic_ui_reads_v1`
  - `advanced_retry_panel_v1`
- Flags never bypass permission checks (`FeatureFlagStore.ensure_permission_gate(...)` remains authoritative).

### Known limitations and deferred UX items
- Core app remains view-model oriented (no final GUI toolkit binding yet).
- Keyboard enhancements are currently limited to baseline shortcut metadata hints in render payloads.
- Advanced uncertain-mutation recovery workflow is deferred pending product/ops policy alignment.
- No contract-breaking API changes were introduced.
