from __future__ import annotations

import pytest

from aris_core_3_app.app import CoreAppShell, build_menu_items as build_core_menu, build_stock_query
from aris_control_center_app.app import ControlCenterAppShell, build_menu_items as build_control_menu
from aris3_client_sdk.models_stock import StockMeta, StockTableResponse, StockTotals
from aris3_client_sdk.models_pos_cash import (
    PosCashMovementListResponse,
    PosCashMovementResponse,
    PosCashSessionCurrentResponse,
    PosCashSessionSummary,
)
from aris3_client_sdk.models_pos_sales import PosSaleHeader, PosSaleResponse
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
