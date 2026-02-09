# ARIS 3 Python Clients (Sprint 5 Day 1)

## Overview
This folder contains the shared Python SDK plus two lightweight Tkinter app shells:

- **aris3_client_sdk**: API configuration, auth session, HTTP client, error mapping, idempotency helpers, tracing, and stock mutation helpers.
- **aris_core_3_app**: Store app shell with login + permission-aware menu placeholders.
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

Payment field requirements:
- `CARD` requires `authorization_code`
- `TRANSFER` requires `bank_name` + `voucher_number`
- Change is only allowed against the cash portion of a payment mix

Cash checkout guard:
- If any `CASH` payment is included, POS checkout verifies there is an open cash session.

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
