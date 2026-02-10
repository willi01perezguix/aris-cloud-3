# ARIS 3 Python Clients (Sprint 5 Day 1)

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
