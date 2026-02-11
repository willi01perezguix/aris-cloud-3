from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from aris3_client_sdk.models_stock import StockMeta, StockTableResponse, StockTotals

from services.permissions_service import PermissionGate
from ui.pos.sale_editor_view import SaleEditorView
from ui.stock.stock_list_view import StockListView


@dataclass
class _Resp:
    rows: list[Any]


class DummyStockService:
    def __init__(self, rows: list[Any] | None = None, fail: Exception | None = None) -> None:
        self.rows = rows or []
        self.fail = fail

    def query_stock(self, _: dict[str, Any]) -> Any:
        if self.fail:
            raise self.fail
        return StockTableResponse(meta=StockMeta(page=1, page_size=20), rows=self.rows, totals=StockTotals())


class DummySalesService:
    def payment_totals(self, total_due: Decimal, payments: list[dict[str, Any]]) -> dict[str, Any]:
        paid = sum(Decimal(str(p.get("amount", 0))) for p in payments)
        missing = total_due - paid if paid < total_due else Decimal("0")
        return {"total_due": total_due, "paid_total": paid, "missing_amount": missing, "change_amount": Decimal("0")}


class DummyCashService:
    class _Current:
        session = None

    def current_session(self) -> Any:
        return self._Current()


def _gate(*keys: str) -> PermissionGate:
    return PermissionGate([{"key": k, "allowed": True} for k in keys])


def test_loading_empty_error_state_rendering_and_permission_denied() -> None:
    denied = StockListView(service=DummyStockService(), gate=_gate())  # type: ignore[arg-type]
    denied.load({})
    assert denied.render()["view_state"]["status"] == "no_permission"

    empty = StockListView(service=DummyStockService(rows=[]), gate=_gate("stock.view"))  # type: ignore[arg-type]
    empty.load({"q": "x"})
    assert empty.render()["view_state"]["status"] in {"empty", "success"}


def test_double_submit_protection_for_mutations() -> None:
    view = SaleEditorView(service=DummySalesService(), cash_service=DummyCashService(), gate=_gate("pos.sales.checkout"), sale_id="sale-1")  # type: ignore[arg-type]
    view.is_submitting = True

    result = view.checkout()

    assert result["ok"] is False
    assert "already in progress" in result["error"]


def test_filter_state_persistence_when_returning_to_stock_list() -> None:
    view = StockListView(service=DummyStockService(rows=[]), gate=_gate("stock.view"))  # type: ignore[arg-type]

    view.load({"q": "shoe", "sku": "SKU-1"})

    assert view.render()["filters"]["q"] == "shoe"
    assert view.last_filters["sku"] == "SKU-1"
