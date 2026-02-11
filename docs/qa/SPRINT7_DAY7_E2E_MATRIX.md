# Sprint 7 Day 7 E2E Matrix

Scope: ARIS-CORE-3 Core App, Control Center, and Python SDK without contract changes.

| ID | Scenario | Preconditions | Steps | Expected Result | Evidence Location |
|---|---|---|---|---|---|
| S7D7-E2E-01 | Auth/session bootstrap + logout | Active user exists; API base URL configured | 1) Login. 2) Call `/aris3/me`. 3) Clear session/logout. | Session token accepted, profile loaded, logout clears local auth state. | `clients/python/tests/e2e/test_sprint7_day7_cross_module.py::test_cross_module_happy_path_and_denied_flows` |
| S7D7-E2E-02 | Effective-permissions loading and UI gating | Role template + user/store policy available | 1) Load effective permissions. 2) Render module gates. | DENY overrides ALLOW, default deny for missing grants, only allowed modules visible. | `clients/python/tests/core_app/test_bootstrap.py`, `clients/python/tests/control_center/test_control_center_day6.py` |
| S7D7-E2E-03 | Stock full-table query + filters + totals | Stock data seeded in sellable location(s) | 1) GET `/aris3/stock` with/without filters. 2) Render totals. | Full-table contract (`meta/rows/totals`) preserved, `TOTAL = RFID + PENDING` in sellable locations. | `clients/python/tests/e2e/test_sprint7_day7_cross_module.py`, `clients/python/tests/core_app/stock/test_stock_module.py` |
| S7D7-E2E-04 | Import EPC validation + submit | `stock.import_epc` permission granted | 1) Submit invalid EPC/qty. 2) Submit valid EPC import payload. | Invalid payload blocked client-side; valid payload posts with transaction + idempotency metadata. | `clients/python/tests/core_app/stock/test_stock_module.py`, `clients/python/tests/e2e/test_sprint7_day7_cross_module.py` |
| S7D7-E2E-05 | Import SKU validation + submit | `stock.import_sku` permission granted | 1) Submit invalid qty/missing SKU. 2) Submit valid SKU import payload. | Validation errors surfaced; valid request accepted without endpoint contract changes. | `clients/python/tests/core_app/stock/test_stock_module.py` |
| S7D7-E2E-06 | Migrate SKU→EPC invariant path | `stock.migrate_sku_to_epc` allowed, PENDING units present | 1) Submit migration payload. 2) Observe expected effect text. | Expected invariant: `PENDING -1`, `RFID +1`, `TOTAL unchanged`. | `clients/python/tests/core_app/stock/test_stock_module.py` |
| S7D7-E2E-07 | POS draft/edit/checkout/cancel | POS permission and store context available | 1) Create draft. 2) Update lines. 3) Checkout via `/actions`. 4) Cancel path validation. | PATCH updates data only; checkout/cancel transitions via `/actions`; lifecycle consistent. | `clients/python/tests/core_app/pos/test_pos_module.py`, `clients/python/tests/e2e/test_sprint7_day7_cross_module.py` |
| S7D7-E2E-08 | Payment rule matrix | POS checkout permission granted | 1) CASH checkout. 2) CARD with/without auth code. 3) TRANSFER with/without bank voucher. 4) Mixed payment case. | CASH requires open session; CARD requires `authorization_code`; TRANSFER requires `bank_name` + `voucher_number`. | `clients/python/tests/test_pos_payment_validation.py`, `clients/python/tests/test_pos_cash_validation.py` |
| S7D7-E2E-09 | Cash-session precondition for CASH | No cash session initially | 1) Attempt CASH checkout. 2) Open cash session. 3) Retry checkout. | First attempt blocked; second succeeds after session open. | `clients/python/tests/core_app/pos/test_pos_module.py`, `clients/python/tests/e2e/test_sprint7_day7_cross_module.py` |
| S7D7-E2E-10 | Control Center user actions | Admin user with user-management grants | 1) Run `set_status`, `set_role`, `reset_password`. 2) Verify operation trace metadata. | Actions post through `/actions`; idempotency + transaction metadata captured. | `clients/python/tests/control_center/test_control_center_day6.py` |
| S7D7-E2E-11 | RBAC precedence visualization + ADMIN ceiling | Base role grants loaded | 1) Build layered effective permissions view. 2) Attempt blocked ADMIN-ceiling grant. | DENY precedence shown; ADMIN-ceiling restrictions enforced. | `clients/python/tests/control_center/test_control_center_day6.py` |
| S7D7-E2E-12 | Settings update (variant fields + return policy) | Settings permissions granted | 1) Load settings. 2) Validate invalid inputs. 3) Save updates. | Validation errors visible; valid PATCH updates accepted with audit metadata. | `clients/python/tests/control_center/test_control_center_day6.py` |

## Execution mode
- Deterministic mode (default): mocked/fixture-backed tests in CI.
- Optional staging mode: `RUN_STAGING_E2E=1 pytest clients/python/tests/e2e -q`.

## Blocker definition
Any failure in auth bootstrap, permissions gating, stock totals contract, POS checkout precondition, or RBAC enforcement is a release blocker for Sprint closure.
