from __future__ import annotations

from aris_core_3_app.app import CoreAppShell, build_menu_items as build_core_menu, build_stock_query
from aris_control_center_app.app import ControlCenterAppShell, build_menu_items as build_control_menu
from aris3_client_sdk.models_stock import StockMeta, StockTableResponse, StockTotals


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
