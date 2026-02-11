# ARIS 3 Python Clients (Sprint 5 Day 7)

## Overview
This folder contains the shared Python SDK plus two lightweight Tkinter app shells:

- **aris3_client_sdk**: API configuration, auth session, HTTP client, error mapping, idempotency helpers, tracing, and stock/transfers mutation helpers.
- **aris_core_3_app**: Store app shell with login + permission-aware menu, stock, POS, and transfers workflows.
- **aris_control_center_app**: Admin app shell with login + permission-aware menu placeholders.

## Setup
```bash
cd clients/python
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration
Copy the example env file and update it:
```bash
cp .env.example .env
```

Supported config keys:
- `ARIS3_ENV` (`dev`, `staging`, `prod`)
- `ARIS3_API_BASE_URL` or `ARIS3_API_BASE_URL_<ENV>`
- `ARIS3_TIMEOUT_SECONDS`
- `ARIS3_RETRIES`
- `ARIS3_VERIFY_SSL`
- `ARIS3_DEFAULT_PAGE_SIZE`
- `ARIS3_DEFAULT_SORT_BY`
- `ARIS3_DEFAULT_SORT_ORDER`
- `ARIS3_TRANSFER_ORIGIN_STORE_ID`
- `ARIS3_TRANSFER_DESTINATION_STORE_ID`

## Run the app shells
```bash
python -m aris_core_3_app.app
python -m aris_control_center_app.app
```

### Stock screen (ARIS CORE 3)
1) Launch the app shell: `python -m aris_core_3_app.app`
2) Login with a user that has `stock.view`
3) Click **Stock** to open the Stock screen with search + mutation actions

Mutation actions (Import EPC, Import SKU, Migrate SKU->EPC) require `STORE_MANAGE`.

### POS screen (ARIS CORE 3)
1) Launch the app shell: `python -m aris_core_3_app.app`
2) Login with a user that has `POS_SALE_VIEW`
3) Click **POS** to open the POS Sales scaffold:
   - Add EPC or SKU lines to the cart
   - Create/update a draft sale
   - Validate and checkout payments (cash/card/transfer)
   - Cancel or refresh a sale

Checkout and cancel actions require `POS_SALE_MANAGE`.

### POS cash operations (ARIS CORE 3)
The POS screen now includes a **Cash Drawer** section that surfaces:
- Current cash session status + metadata
- Open/Cash In/Cash Out/Close actions (permission-gated)
- Recent cash movements
- Day close button (manager/admin permission-gated)

Permissions:
- `POS_CASH_VIEW` to view cash sessions/movements
- `POS_CASH_MANAGE` to open/adjust/close cash sessions
- `POS_CASH_DAY_CLOSE` to close the business day

Cash guardrails:
- `CASH` checkout requires an open cash session
- Cash out is prevented when it would drive expected cash negative
- Change is only allowed against the cash portion of payments


### Inventory Counts screen (ARIS CORE 3)
1) Launch the app shell: `python -m aris_core_3_app.app`
2) Login with a user that has `inventory.counts.view`
3) Click **Inventory Counts** to open the inventory count workflow:
   - Start a count for a store (Option A lock awareness)
   - Execute lifecycle actions (Pause/Resume/Close/Cancel/Reconcile) with state-aware controls
   - Submit EPC/SKU scan batches with client-side validation
   - Refresh count status and lock indicator

Permissions:
- `inventory.counts.view` (or `INVENTORY_COUNT_VIEW`) to view
- `inventory.counts.manage` (or `INVENTORY_COUNT_MANAGE`) to mutate lifecycle and scans

### Transfers screen (ARIS CORE 3)
1) Launch the app shell: `python -m aris_core_3_app.app`
2) Login with a user that has `TRANSFER_VIEW`
3) Click **Transfers** to open the Transfers workflow:
   - Filter and search transfers by status, origin/destination, and date range
   - View transfer header, line snapshots, and movement summary
   - Create draft transfers, edit draft data, dispatch, receive, report shortages, resolve shortages, or cancel

Permissions:
- `TRANSFER_VIEW` to view the transfers list
- `TRANSFER_MANAGE` to create or mutate transfers
- LOST_IN_ROUTE resolutions require manager/admin role

Transfers lifecycle:
- `DRAFT` → `DISPATCHED` → `RECEIVED` or `PARTIAL_RECEIVED`
- Shortage reporting and resolution can occur while `DISPATCHED` or `PARTIAL_RECEIVED`
- `CANCELLED` is allowed from `DRAFT` or `DISPATCHED` (policy-dependent)

## SDK smoke CLI
```bash
python examples/cli_smoke.py health
python examples/cli_smoke.py login --username <user> --password <pass>
python examples/cli_smoke.py me
python examples/cli_smoke.py permissions
```

## Stock smoke CLI
```bash
python examples/stock_smoke.py stock --sku <sku> --page 1 --page-size 50
```

## Stock mutation smoke CLIs
```bash
python examples/stock_import_epc_smoke.py --input /path/to/import_epc.json
python examples/stock_import_sku_smoke.py --input /path/to/import_sku.json
python examples/stock_migrate_smoke.py --input /path/to/migrate.json
```

## POS smoke CLIs
```bash
python examples/pos_create_sale_smoke.py --store-id <store_id> --sku SKU-1 --qty 1 --unit-price 10 --location-code LOC-1 --pool P1
python examples/pos_add_items_smoke.py --sale-id <sale_id> --sku SKU-1 --qty 1 --unit-price 10 --location-code LOC-1 --pool P1
python examples/pos_checkout_smoke.py --sale-id <sale_id> --cash 10
python examples/pos_cancel_sale_smoke.py --sale-id <sale_id>
```

## POS cash smoke CLIs
```bash
python examples/pos_cash_open_smoke.py --store-id <store_id> --opening-amount 100 --business-date 2024-01-01 --timezone UTC
python examples/pos_cash_in_smoke.py --store-id <store_id> --amount 20 --reason "Midday float"
python examples/pos_cash_out_smoke.py --store-id <store_id> --amount 10 --reason "Safe drop"
python examples/pos_cash_close_smoke.py --store-id <store_id> --counted-cash 110 --reason "End of shift"
python examples/pos_day_close_smoke.py --store-id <store_id> --business-date 2024-01-01 --timezone UTC
```


## Inventory Counts smoke CLIs
```bash
python examples/inv_count_start_smoke.py --store-id <store_id>
python examples/inv_count_scan_batch_smoke.py --count-id <count_id> --epc <epc_hex24>
python examples/inv_count_pause_resume_smoke.py --count-id <count_id>
python examples/inv_count_close_smoke.py --count-id <count_id>
python examples/inv_count_reconcile_smoke.py --count-id <count_id>
python examples/inv_count_summary_diff_smoke.py --count-id <count_id>
python examples/inv_count_export_smoke.py --count-id <count_id>
```

## Transfers smoke CLIs
```bash
python examples/transfers_create_smoke.py --origin-store-id <origin_store_id> --destination-store-id <destination_store_id>
python examples/transfers_dispatch_smoke.py --transfer-id <transfer_id>
python examples/transfers_receive_smoke.py --transfer-id <transfer_id> --input /path/to/receive.json
python examples/transfers_report_shortages_smoke.py --transfer-id <transfer_id> --input /path/to/shortages.json
python examples/transfers_resolve_shortages_smoke.py --transfer-id <transfer_id> --input /path/to/resolve.json
python examples/transfers_cancel_smoke.py --transfer-id <transfer_id>
```

Payment field requirements:
- `CARD` requires `authorization_code`
- `TRANSFER` requires `bank_name` + `voucher_number`
- Change is only allowed against the cash portion of a payment mix

Cash checkout guard:
- If any `CASH` payment is included, POS checkout verifies there is an open cash session.
 - Cash session operations include `transaction_id` + `Idempotency-Key` for safe retries.

Troubleshooting:
- When API errors occur, capture the `trace_id` displayed in CLI/UI to correlate backend logs.

## SDK mutation example (idempotency)
```python
from aris3_client_sdk import ApiSession, load_config, new_idempotency_keys
from aris3_client_sdk.clients.stock_client import StockClient

config = load_config()
session = ApiSession(config)
client = StockClient(http=session._http(), access_token=session.token)
keys = new_idempotency_keys()

response = client.import_epc(
    [
        {
            "sku": "SKU-1",
            "description": "Blue Jacket",
            "var1_value": "Blue",
            "var2_value": "L",
            "epc": "A" * 24,
            "location_code": "LOC-1",
            "pool": "P1",
            "status": "RFID",
            "location_is_vendible": True,
            "qty": 1,
        }
    ],
    transaction_id=keys.transaction_id,
    idempotency_key=keys.idempotency_key,
)
print(response.trace_id)
```

### Troubleshooting
- **Validation errors**: client-side validation errors include row index + field details.
- **API errors**: check `trace_id` in the response or error payload to correlate backend logs.

## Tests
```bash
pytest
```

## Architecture notes
- **SDK owns**: config loading, HTTP transport, auth token storage, API error mapping, tracing, and API clients.
- **Apps own**: UI screens, permission-driven enablement, and any domain-specific workflows.

## Windows storage
Sessions are stored under the user data directory (via `platformdirs`) in `session.json`.


Sprint 5 client capabilities summary:
- Stock, POS Sales, POS Cash, Transfers, and Inventory Counts workflows are now available in SDK, CLI, and ARIS CORE 3 shell.
- All critical inventory count mutations include transaction_id + idempotency support.
- Backend failures surface trace_id in CLI and UI for operational troubleshooting.


## Sprint 6 Day 1 additions
- SDK: new ReportsClient and ExportsClient with typed models for report/expor payloads.
- ARIS CORE 3: Reports screen (filters, KPI summary, daily rows preview, export trigger/history).
- Control Center: read-only Effective Permissions Inspector with grouped matrix and deny markers.
- New smoke scripts:
  - `python examples/reports_overview_smoke.py --store-id <store_id> --from-date YYYY-MM-DD --to-date YYYY-MM-DD`
  - `python examples/reports_daily_smoke.py --store-id <store_id> --from-date YYYY-MM-DD --to-date YYYY-MM-DD`
  - `python examples/reports_calendar_smoke.py --store-id <store_id> --from-date YYYY-MM-DD --to-date YYYY-MM-DD`
  - `python examples/exports_request_smoke.py --source-type reports_daily --format csv --store-id <store_id>`
  - `python examples/exports_status_smoke.py --export-id <export_id>`
  - `python examples/exports_download_smoke.py --export-id <export_id> --out ./export.bin`

Permissions notes:
- Reports/Exports require `REPORTS_VIEW` (or `reports.view`).
- Control Center inspector requires `rbac.view`.
- API failures always display `trace_id`; include it in support/audit tickets.


## Sprint 6 Day 2 additions
- Advanced reports filter normalization (`store_id`, date range, timezone, payment method, grouping/granularity aliases).
- Export manager flow with request, status refresh/history, retry failed, artifact resolution, and robust wait helper (`COMPLETED`/`FAILED`/`EXPIRED`/`NOT_FOUND`).
- ARIS CORE 3 Reports screen now includes Apply/Reset filters, sortable primary table, and export manager panel.
- Control Center includes a read-only **Operational Insights** panel (permission-gated).
- Windows packaging scaffold under `clients/python/packaging` with spec templates and build scripts.

### Packaging quickstart
```bash
cd clients/python/packaging
# PowerShell
./build_core.ps1 -DryRun
./build_control_center.ps1 -DryRun
```

### Packaging dry-run + diagnostics (Sprint 8 Day 8)
Run deterministic dry-runs locally from `clients/python/packaging`:

```powershell
./build_core.ps1 -DryRun
./build_control_center.ps1 -DryRun
# CI-equivalent behavior (venv warning only):
./build_core.ps1 -DryRun -CiMode
./build_control_center.ps1 -DryRun -CiMode
```

Expected artifacts/log outputs:
- Local default outputs:
  - `clients/python/packaging/dist/core/`
  - `clients/python/packaging/dist/control_center/`
- CI smoke diagnostics root:
  - `clients/python/packaging/temp/artifacts/`
  - `clients/python/packaging/temp/artifacts/core/build_core_dryrun.log`
  - `clients/python/packaging/temp/artifacts/control_center/build_control_center_dryrun.log`
- Each run writes metadata + summary in resolved output dir:
  - `*_packaging_metadata.json`
  - `build_summary.json`

Common packaging failures + quick fixes:
- **venv is not active**: activate your virtualenv before local packaging runs.
- **Path/outdir confusion**: pass `-OutDir` once; scripts normalize to an absolute resolved path.
- **pyinstaller not found**: install dependencies (`pip install -r ../requirements.txt`) and ensure `pyinstaller` is available in the active venv.


## Sprint 6 Day 3 additions
- SDK media resolver support via `MediaClient` (`variant -> sku -> placeholder` fallback).
- Stock/POS screens now expose image source + thumbnail URL text with non-blocking fallback behavior and `Show images` toggles.
- Control Center now has a read-only **Media Inspector** panel (SKU + var1 + var2 lookup).
- New media smoke scripts:
  - `python examples/media_resolve_smoke.py --sku SKU-1 --var1 Blue --var2 L`
  - `python examples/media_stock_preview_smoke.py --page-size 50`
  - `python examples/media_pos_item_smoke.py --sku SKU-1`
- Packaging step-up:
  - `packaging/build_core.ps1` + `build_control_center.ps1` now run preflight checks and write `build_summary.json`.
  - Added `packaging/build_all.ps1` and `packaging/installer_placeholder.ps1`.
  - Dist folders standardized to `packaging/dist/core` and `packaging/dist/control_center`.

### Media fallback rules in UI
- Prefer backend-provided variant image fields on stock/POS records.
- If absent and images enabled, resolve by `sku + var1 + var2` via SDK helper.
- Fallback to SKU-level match, then final placeholder (`placeholder://aris-image`).

### Packaging usage (Windows)
```powershell
cd clients/python/packaging
./build_core.ps1 -DryRun
./build_control_center.ps1 -DryRun
./build_all.ps1 -DryRun
```

## Sprint 6 Day 4 release hardening

### HTTP timeout/retry defaults
- `ARIS3_CONNECT_TIMEOUT_SECONDS` (default `5`)
- `ARIS3_READ_TIMEOUT_SECONDS` (default `15`)
- `ARIS3_RETRIES` (default `3`, read-only retries)
- `ARIS3_RETRY_BACKOFF_SECONDS` (default `0.3`)

### QA matrix runner
```bash
python clients/python/tools/qa_matrix_runner.py --env clients/python/.env --store <store_id> --fail-on critical --quick
```
Outputs:
- `artifacts/qa/client_qa_matrix_<timestamp>.json`
- `artifacts/qa/client_qa_matrix_<timestamp>.md`

### Support bundle
```bash
python clients/python/tools/create_support_bundle.py --output-dir artifacts/support
```
Output:
- `artifacts/support/support_bundle_<timestamp>.zip`

### Packaging verification flow
```bash
python clients/python/tools/packaging_verify.py --packaging-root clients/python/packaging
```
Outputs:
- `artifacts/packaging/build_manifest_<timestamp>.json`
- `artifacts/packaging/packaging_verify_<timestamp>.md`

### Launch checks
```bash
python -m aris_core_3_app.app
python -m aris_control_center_app.app
```

## Sprint 7 Day 2 SDK hardening (Python)

### Quickstart (SDK-focused)
```bash
cd clients/python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ./aris3_client_sdk[dev]
python examples/sdk_quickstart.py
```

### SDK hardening highlights
- Resilient HTTP transport with configurable base URL/timeouts/retries/backoff/connection pool.
- Retry defaults are safe for reads (`GET`/`HEAD`) with explicit per-call mutation retry opt-in.
- Structured SDK exceptions now normalize `status_code`, `code`, `message`, `details`, `trace_id`, and `raw_payload`.
- `AuthStore` now safely handles corrupted session files and supports clean session clear/logout flows.
- Centralized idempotency helpers (`transaction_id`, `idempotency_key`, header helper) for critical mutations.
- Trace context propagation via `X-Trace-ID` plus optional tenant/app/device metadata headers in base clients.

### Runnable examples for app teams
- Login + me: `python examples/cli_smoke.py login --username <user> --password <pass>` then `python examples/cli_smoke.py me`
- Stock full-table query (`meta/rows/totals`): `python examples/stock_smoke.py stock --sku <sku> --page 1 --page-size 50`
- Idempotent mutation helper usage: `python examples/sdk_quickstart.py`
- Structured error handling example: `python examples/sdk_quickstart.py`

### Compatibility statement
All Sprint 7 Day 2 SDK changes are non-breaking with the frozen ARIS API contract.
