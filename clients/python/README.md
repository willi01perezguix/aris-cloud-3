# ARIS 3 Python Clients (Sprint 5 Day 1)

## Overview
This folder contains the shared Python SDK plus two lightweight Tkinter app shells:

- **aris3_client_sdk**: API configuration, auth session, HTTP client, error mapping, idempotency helpers, tracing.
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
3) Click **Stock** to open the read-only Stock screen

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

## Tests
```bash
pytest
```

## Architecture notes
- **SDK owns**: config loading, HTTP transport, auth token storage, API error mapping, tracing, and API clients.
- **Apps own**: UI screens, permission-driven enablement, and any domain-specific workflows.

## Windows storage
Sessions are stored under the user data directory (via `platformdirs`) in `session.json`.
