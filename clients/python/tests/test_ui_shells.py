from __future__ import annotations

import pytest

from aris_core_3_app.app import CoreAppShell, build_menu_items as build_core_menu, build_stock_query
from aris_control_center_app.app import ControlCenterAppShell, build_menu_items as build_control_menu
from aris3_client_sdk.models import PermissionEntry, UserResponse
from aris3_client_sdk.models_stock import StockMeta, StockTableResponse, StockTotals
from aris3_client_sdk.models_pos_cash import (
    PosCashMovementListResponse,
    PosCashMovementResponse,
    PosCashSessionCurrentResponse,
    PosCashSessionSummary,
)
from aris3_client_sdk.models_pos_sales import PosSaleHeader, PosSaleResponse
from aris3_client_sdk.models_inventory_counts import CountHeader
from aris3_client_sdk.models_transfers import (
    TransferHeader,
    TransferLineResponse,
    TransferLineSnapshot,
    TransferMovementSummary,
    TransferResponse,
)
from aris3_client_sdk.stock_validation import ValidationIssue


@pytest.fixture(autouse=True)
def _set_api_base_url(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")


def test_core_app_shell_headless() -> None:
    app = CoreAppShell()
    app.start(headless=True)


def test_control_center_app_shell_headless() -> None:
    app = ControlCenterAppShell()
    app.start(headless=True)


def test_core_menu_permissions() -> None:
    allowed = {"stock.view", "reports.view"}
    items = build_core_menu(allowed)
    enabled = {item.label for item in items if item.enabled}
    assert enabled == {"Stock", "Reports"}


def test_control_center_menu_permissions() -> None:
    allowed = {"users.view", "audit.view"}
    items = build_control_menu(allowed)
    enabled = {item.label for item in items if item.enabled}
    assert enabled == {"Users", "Audit"}


def test_stock_screen_initializes_filters() -> None:
    app = CoreAppShell()
    app._ensure_stock_filter_vars()
    assert "sku" in app.stock_filter_vars
    assert "location_code" in app.stock_filter_vars


def test_stock_search_calls_client_with_filters() -> None:
    app = CoreAppShell()
    filters = {"q": "Blue", "sku": "SKU-1", "from": "2024-01-01T00:00:00Z", "to": None}
    query = build_stock_query(filters, page=1, page_size=25, sort_by="created_at", sort_order="desc")

    class FakeClient:
        def __init__(self) -> None:
            self.query = None

        def get_stock(self, received_query):
            self.query = received_query
            return StockTableResponse(
                meta=StockMeta(page=1, page_size=25, sort_by="created_at", sort_dir="desc"),
                rows=[],
                totals=StockTotals(total_rows=0, total_rfid=0, total_pending=0, total_units=0),
            )

    fake = FakeClient()
    app._request_stock(query, client=fake)
    assert fake.query.sku == "SKU-1"
    assert fake.query.q == "Blue"


def test_stock_permission_denied_state() -> None:
    app = CoreAppShell()
    app.allowed_permissions = set()
    assert app._is_stock_allowed() is False


def test_stock_action_permission_state() -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"STORE_MANAGE"}
    assert app._can_manage_stock() is True
    app.allowed_permissions = {"STORE_VIEW"}
    assert app._can_manage_stock() is False


def test_stock_action_submit_calls_client() -> None:
    app = CoreAppShell()

    class FakeClient:
        def __init__(self) -> None:
            self.called = False
            self.payload = None

        def import_epc(self, lines, transaction_id=None, idempotency_key=None):
            self.called = True
            self.payload = (lines, transaction_id, idempotency_key)

            class Response:
                trace_id = "trace"
                processed = 1

            return Response()

    fake = FakeClient()
    app._submit_stock_import_epc(
        [{"sku": "SKU-1", "epc": "A" * 24, "location_code": "LOC-1", "pool": "P1", "status": "RFID", "qty": 1}],
        transaction_id="txn-1",
        idempotency_key="idem-1",
        client=fake,
    )
    assert fake.called is True
    assert fake.payload[1] == "txn-1"


def test_stock_action_validation_formatting() -> None:
    app = CoreAppShell()
    issues = [
        ValidationIssue(row_index=0, field="epc", reason="missing"),
        ValidationIssue(row_index=None, field="lines", reason="empty"),
    ]
    formatted = app._format_validation_issues(issues)
    assert "row 0 epc: missing" in formatted
    assert "lines: empty" in formatted


def test_pos_permission_gating() -> None:
    app = CoreAppShell()
    app.allowed_permissions = set()
    assert app._is_pos_allowed() is False
    app.allowed_permissions = {"POS_SALE_VIEW"}
    assert app._is_pos_allowed() is True
    app.allowed_permissions = {"POS_SALE_MANAGE"}
    assert app._can_manage_pos() is True


def test_pos_cash_permission_gating() -> None:
    app = CoreAppShell()
    app.allowed_permissions = set()
    assert app._is_pos_cash_allowed() is False
    app.allowed_permissions = {"POS_CASH_VIEW"}
    assert app._is_pos_cash_allowed() is True
    app.allowed_permissions = {"POS_CASH_MANAGE"}
    assert app._can_manage_pos_cash() is True
    app.allowed_permissions = {"POS_CASH_DAY_CLOSE"}
    assert app._can_day_close_pos_cash() is True


def test_pos_totals_initialize() -> None:
    app = CoreAppShell()
    app._update_pos_totals()
    assert "total_due" in app.pos_totals_var.get()


def test_pos_checkout_validation_and_call() -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"POS_SALE_MANAGE"}
    app.pos_store_id_var.set("store-1")
    app.pos_cash_amount_var.set("10.00")
    app.pos_state.sale = PosSaleResponse(
        header=PosSaleHeader(
            id="sale-1",
            tenant_id="tenant-1",
            store_id="store-1",
            status="DRAFT",
            total_due=10.0,
            paid_total=0.0,
            balance_due=10.0,
            change_due=0.0,
        ),
        lines=[],
        payments=[],
        payment_summary=[],
        refunded_totals=None,
        exchanged_totals=None,
        net_adjustment=None,
        return_events=[],
    )

    class FakePosClient:
        def __init__(self) -> None:
            self.called = False

        def sale_action(self, sale_id, action, payload, idempotency_key=None):
            self.called = True
            return app.pos_state.sale

    class FakeCashClient:
        def get_current_session(self, store_id=None):
            return PosCashSessionCurrentResponse(session=PosCashSessionSummary(id="cash-1", status="OPEN"))

    fake_client = FakePosClient()
    app._checkout_pos_sale(client=fake_client, cash_client=FakeCashClient())
    assert fake_client.called is True


def _sample_transfer(status: str = "DRAFT") -> TransferResponse:
    return TransferResponse(
        header=TransferHeader(
            id="transfer-1",
            tenant_id="tenant-1",
            origin_store_id="origin-1",
            destination_store_id="dest-1",
            status=status,
            created_at="2024-01-01T00:00:00Z",
        ),
        lines=[
            TransferLineResponse(
                id="line-1",
                line_type="SKU",
                qty=2,
                received_qty=0,
                outstanding_qty=2,
                shortage_status=None,
                resolution_status=None,
                snapshot=TransferLineSnapshot(
                    sku="SKU-1",
                    location_code="LOC",
                    pool="P1",
                    location_is_vendible=True,
                ),
                created_at="2024-01-01T00:00:00Z",
            )
        ],
        movement_summary=TransferMovementSummary(
            dispatched_lines=0,
            dispatched_qty=0,
            pending_reception=False,
            shortages_possible=False,
        ),
    )


def test_transfer_permission_gating() -> None:
    app = CoreAppShell()
    app.allowed_permissions = set()
    assert app._is_transfers_allowed() is False
    app.allowed_permissions = {"TRANSFER_VIEW"}
    assert app._is_transfers_allowed() is True
    app.allowed_permissions = {"TRANSFER_MANAGE"}
    assert app._can_manage_transfers() is True


def test_transfer_action_visibility_by_state() -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"TRANSFER_MANAGE"}
    app.session.user = UserResponse(id="user-1", username="u", store_id="dest-1", role="USER")
    app.transfer_state.selected = _sample_transfer(status="DISPATCHED")

    class FakeButton:
        def __init__(self) -> None:
            self.state = None

        def configure(self, state=None):
            self.state = state

    app.transfer_action_buttons = {
        "Create": FakeButton(),
        "Update Draft": FakeButton(),
        "Dispatch": FakeButton(),
        "Receive": FakeButton(),
        "Report Shortages": FakeButton(),
        "Resolve Shortages": FakeButton(),
        "Cancel": FakeButton(),
        "Refresh Detail": FakeButton(),
    }
    app._update_transfer_action_buttons()
    assert app.transfer_action_buttons["Dispatch"].state == "disabled"
    assert app.transfer_action_buttons["Receive"].state == "normal"


def test_transfer_action_calls_sdk(monkeypatch) -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"TRANSFER_MANAGE"}
    app.session.user = UserResponse(id="user-1", username="u", store_id="dest-1", role="MANAGER")
    app.transfer_state.selected = _sample_transfer(status="DRAFT")

    called = {}

    class FakeTransfersClient:
        def __init__(self, http, access_token=None) -> None:
            pass

        def transfer_action(self, transfer_id, action, payload, **kwargs):
            called["action"] = action
            return _sample_transfer(status="DISPATCHED")

    class ImmediateThread:
        def __init__(self, target, daemon=None) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    monkeypatch.setattr("aris_core_3_app.app.TransfersClient", FakeTransfersClient)
    monkeypatch.setattr("aris_core_3_app.app.threading.Thread", ImmediateThread)

    app._submit_transfer_request("dispatch", payload={})
    assert called["action"] == "dispatch"


def test_pos_checkout_validation_errors_rendered() -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"POS_SALE_MANAGE"}
    app.pos_store_id_var.set("store-1")
    app.pos_card_amount_var.set("10.00")
    app.pos_state.sale = PosSaleResponse(
        header=PosSaleHeader(
            id="sale-2",
            tenant_id="tenant-1",
            store_id="store-1",
            status="DRAFT",
            total_due=10.0,
            paid_total=0.0,
            balance_due=10.0,
            change_due=0.0,
        ),
        lines=[],
        payments=[],
        payment_summary=[],
        refunded_totals=None,
        exchanged_totals=None,
        net_adjustment=None,
        return_events=[],
    )

    class FakePosClient:
        def __init__(self) -> None:
            self.called = False

        def sale_action(self, sale_id, action, payload, idempotency_key=None):
            self.called = True
            return app.pos_state.sale

    app._checkout_pos_sale(client=FakePosClient())
    assert "authorization_code" in app.pos_validation_var.get()


def test_pos_cash_session_guard() -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"POS_SALE_MANAGE"}
    app.pos_store_id_var.set("store-1")
    app.pos_cash_amount_var.set("10.00")
    app.pos_state.sale = PosSaleResponse(
        header=PosSaleHeader(
            id="sale-3",
            tenant_id="tenant-1",
            store_id="store-1",
            status="DRAFT",
            total_due=10.0,
            paid_total=0.0,
            balance_due=10.0,
            change_due=0.0,
        ),
        lines=[],
        payments=[],
        payment_summary=[],
        refunded_totals=None,
        exchanged_totals=None,
        net_adjustment=None,
        return_events=[],
    )

    class FakePosClient:
        def __init__(self) -> None:
            self.called = False

        def sale_action(self, sale_id, action, payload, idempotency_key=None):
            self.called = True
            return app.pos_state.sale

    class FakeCashClient:
        def get_current_session(self, store_id=None):
            return PosCashSessionCurrentResponse(session=None)

    fake_client = FakePosClient()
    app._checkout_pos_sale(client=fake_client, cash_client=FakeCashClient())
    assert fake_client.called is False
    assert "CASH checkout" in app.pos_validation_var.get()


def test_pos_cash_session_status_not_open_blocks_checkout() -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"POS_SALE_MANAGE"}
    app.pos_store_id_var.set("store-1")
    app.pos_cash_amount_var.set("10.00")
    app.pos_state.sale = PosSaleResponse(
        header=PosSaleHeader(
            id="sale-4",
            tenant_id="tenant-1",
            store_id="store-1",
            status="DRAFT",
            total_due=10.0,
            paid_total=0.0,
            balance_due=10.0,
            change_due=0.0,
        ),
        lines=[],
        payments=[],
        payment_summary=[],
        refunded_totals=None,
        exchanged_totals=None,
        net_adjustment=None,
        return_events=[],
    )

    class FakePosClient:
        def __init__(self) -> None:
            self.called = False

        def sale_action(self, sale_id, action, payload, idempotency_key=None):
            self.called = True
            return app.pos_state.sale

    class FakeCashClient:
        def get_current_session(self, store_id=None):
            return PosCashSessionCurrentResponse(session=PosCashSessionSummary(id="cash-2", status="CLOSED"))

    fake_client = FakePosClient()
    app._checkout_pos_sale(client=fake_client, cash_client=FakeCashClient())
    assert fake_client.called is False
    assert "CASH checkout" in app.pos_validation_var.get()


def test_pos_cash_open_calls_client() -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"POS_CASH_MANAGE"}
    app.pos_store_id_var.set("store-1")
    app.pos_cash_opening_amount_var.set("10.00")
    app.pos_cash_business_date_var.set("2024-01-01")
    app.pos_cash_timezone_var.set("UTC")

    class FakeCashClient:
        def __init__(self) -> None:
            self.called = False

        def cash_action(self, action, payload, idempotency_key=None):
            self.called = True
            return PosCashSessionSummary(id="cash-3", status="OPEN")

        def get_current_session(self, store_id=None):
            return PosCashSessionCurrentResponse(session=PosCashSessionSummary(id="cash-3", status="OPEN"))

        def get_movements(self, store_id=None, limit=None):
            return PosCashMovementListResponse(
                rows=[PosCashMovementResponse(id="move-1", movement_type="OPEN")],
                total=1,
            )

    fake_client = FakeCashClient()
    app._open_cash_session(client=fake_client, async_mode=False)
    assert fake_client.called is True


def test_pos_cash_day_close_permission_gate() -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"POS_CASH_VIEW"}
    app.pos_store_id_var.set("store-1")
    app.pos_cash_business_date_var.set("2024-01-01")
    app.pos_cash_timezone_var.set("UTC")

    class FakeCashClient:
        def __init__(self) -> None:
            self.called = False

        def day_close(self, payload, idempotency_key=None):
            self.called = True
            return None

    fake_client = FakeCashClient()
    app._day_close_cash(client=fake_client, async_mode=False)
    assert fake_client.called is False


def test_inventory_permission_gating() -> None:
    app = CoreAppShell()
    app.allowed_permissions = set()
    assert app._is_inventory_counts_allowed() is False
    app.allowed_permissions = {"inventory.counts.view"}
    assert app._is_inventory_counts_allowed() is True


def test_inventory_action_visibility_by_state() -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"INVENTORY_COUNT_MANAGE"}
    app.inventory_state.selected = CountHeader(id="c1", store_id="s1", state="ACTIVE")

    class FakeButton:
        def __init__(self) -> None:
            self.state = None

        def configure(self, state=None):
            self.state = state

    app.inventory_action_buttons = {
        "PAUSE": FakeButton(),
        "RESUME": FakeButton(),
        "CLOSE": FakeButton(),
        "CANCEL": FakeButton(),
        "RECONCILE": FakeButton(),
    }
    app._update_inventory_action_buttons()
    assert app.inventory_action_buttons["PAUSE"].state == "normal"
    assert app.inventory_action_buttons["RESUME"].state == "disabled"


def test_inventory_scan_submit_invokes_sdk(monkeypatch) -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"INVENTORY_COUNT_MANAGE"}
    app.inventory_count_id_var.set("c1")
    app.inventory_scan_sku_var.set("SKU-1")

    called = {}

    class FakeClient:
        def __init__(self, http=None, access_token=None) -> None:
            pass

        def submit_scan_batch(self, count_id, payload, **kwargs):
            called["count_id"] = count_id
            called["payload"] = payload

            class Resp:
                accepted = 1
                rejected = 0

            return Resp()

    monkeypatch.setattr("aris_core_3_app.app.InventoryCountsClient", FakeClient)
    app._submit_inventory_scan_batch()
    assert called["count_id"] == "c1"


def test_inventory_trace_id_shown_on_error(monkeypatch) -> None:
    from aris3_client_sdk.exceptions import ApiError

    app = CoreAppShell()
    app.inventory_count_id_var.set("c1")
    app.inventory_scan_sku_var.set("SKU-1")

    class FakeClient:
        def __init__(self, http=None, access_token=None) -> None:
            pass

        def submit_scan_batch(self, count_id, payload, **kwargs):
            raise ApiError(code="ERR", message="boom", details=None, trace_id="trace-x", status_code=500)

    monkeypatch.setattr("aris_core_3_app.app.InventoryCountsClient", FakeClient)
    app._submit_inventory_scan_batch()
    assert "trace-x" in app.inventory_trace_var.get()


def test_reports_permission_gating() -> None:
    app = CoreAppShell()
    app.allowed_permissions = set()
    assert app._is_reports_allowed() is False
    app.allowed_permissions = {"REPORTS_VIEW"}
    assert app._is_reports_allowed() is True


def test_reports_filter_state_initializes() -> None:
    app = CoreAppShell()
    app.reports_store_id_var.set("store-1")
    payload = app._report_filter_payload()
    assert payload.store_id == "store-1"


def test_reports_export_action_triggers_client_call() -> None:
    app = CoreAppShell()
    app.allowed_permissions = {"REPORTS_VIEW"}
    app.reports_store_id_var.set("store-1")

    class FakeClient:
        def request_export(self, payload, idempotency_key=None):
            from aris3_client_sdk.models_exports import ExportStatus
            return ExportStatus.model_validate({
                "export_id": "exp-1", "tenant_id": "tenant-1", "store_id": "store-1",
                "source_type": "reports_daily", "format": "csv", "filters_snapshot": {}, "status": "READY",
                "row_count": 1, "checksum_sha256": "abc", "failure_reason_code": None, "generated_by_user_id": "u1",
                "generated_at": None, "trace_id": "trace-1", "file_size_bytes": 10, "content_type": "text/csv",
                "file_name": "report.csv", "created_at": "2024-01-01T00:00:00Z", "updated_at": None
            })

    import aris_core_3_app.app as core_app_mod
    original = core_app_mod.ExportsClient
    core_app_mod.ExportsClient = lambda http, access_token: FakeClient()
    try:
        app._request_report_export()
    finally:
        core_app_mod.ExportsClient = original
    assert "exp-1" in app.reports_export_status_var.get()


def test_control_center_permissions_grouping() -> None:
    from aris_control_center_app.app import group_permissions
    grouped = group_permissions([
        PermissionEntry(key="inventory.view", allowed=True),
        PermissionEntry(key="inventory.manage", allowed=False),
    ])
    assert "inventory" in grouped


def test_regression_module_imports() -> None:
    import aris3_client_sdk.clients.stock_client
    import aris3_client_sdk.clients.pos_sales_client
    import aris3_client_sdk.clients.pos_cash_client
    import aris3_client_sdk.clients.transfers_client
    import aris3_client_sdk.clients.inventory_counts_client
