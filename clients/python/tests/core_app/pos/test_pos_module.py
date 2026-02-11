from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.models_pos_cash import (
    PosCashMovementListResponse,
    PosCashMovementResponse,
    PosCashSessionCurrentResponse,
    PosCashSessionSummary,
)
from aris3_client_sdk.models_pos_sales import (
    PosPaymentResponse,
    PosSaleHeader,
    PosSaleLine,
    PosSaleLineSnapshot,
    PosSaleResponse,
)

from services.permissions_service import PermissionGate
from services.pos_cash_service import PosCashService
from services.pos_sales_service import PosSalesService
from ui.pos.cash_movements_view import CashMovementsView
from ui.pos.cash_session_view import CashSessionView
from ui.pos.sale_editor_view import SaleEditorView
from ui.pos.sales_list_view import SalesListView


@dataclass
class FakePosSalesClient:
    sale: PosSaleResponse
    list_rows: list[PosSaleResponse]
    fail_get: Exception | None = None
    fail_action: Exception | None = None
    fail_update: Exception | None = None
    checkout_calls: list[dict[str, Any]] = None  # type: ignore[assignment]
    cancel_calls: list[dict[str, Any]] = None  # type: ignore[assignment]
    last_update: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.checkout_calls = []
        self.cancel_calls = []

    def create_sale(self, payload: Any, transaction_id: str | None = None, idempotency_key: str | None = None) -> PosSaleResponse:
        assert transaction_id
        assert idempotency_key
        return self.sale

    def update_sale(self, sale_id: str, payload: Any, transaction_id: str | None = None, idempotency_key: str | None = None) -> PosSaleResponse:
        if self.fail_update:
            raise self.fail_update
        self.last_update = {"sale_id": sale_id, "payload": payload, "transaction_id": transaction_id, "idempotency_key": idempotency_key}
        return self.sale

    def get_sale(self, sale_id: str) -> PosSaleResponse:
        if self.fail_get:
            raise self.fail_get
        return self.sale

    def list_sales(self, filters: Any = None):
        class _R:
            def __init__(self, rows: list[PosSaleResponse]) -> None:
                self.rows = rows

        return _R(self.list_rows)

    def sale_action(self, sale_id: str, action: str, payload: Any, transaction_id: str | None = None, idempotency_key: str | None = None) -> PosSaleResponse:
        if self.fail_action:
            raise self.fail_action
        record = {
            "sale_id": sale_id,
            "action": action,
            "payload": payload,
            "transaction_id": transaction_id,
            "idempotency_key": idempotency_key,
        }
        if action == "checkout":
            self.checkout_calls.append(record)
        if action == "cancel":
            self.cancel_calls.append(record)
        return self.sale


@dataclass
class FakePosCashClient:
    session: PosCashSessionSummary | None
    fail_action: Exception | None = None

    def get_current_session(self, **_: Any) -> PosCashSessionCurrentResponse:
        return PosCashSessionCurrentResponse(session=self.session)

    def cash_action(self, action: str, payload: Any, transaction_id: str | None = None, idempotency_key: str | None = None) -> PosCashSessionSummary:
        if self.fail_action:
            raise self.fail_action
        assert transaction_id
        assert idempotency_key
        data = payload.model_dump(mode="json", exclude_none=True)
        self.session = PosCashSessionSummary(
            id="cash-1",
            store_id=data.get("store_id"),
            status="OPEN" if action != "CLOSE" else "CLOSED",
            opening_amount=100,
            business_date=date(2026, 1, 5),
            timezone="UTC",
        )
        return self.session

    def get_movements(self, **_: Any) -> PosCashMovementListResponse:
        return PosCashMovementListResponse(
            rows=[
                PosCashMovementResponse(
                    id="mov-1",
                    movement_type="CASH_IN",
                    amount=Decimal("30.00"),
                )
            ],
            total=1,
        )


class FakeSession:
    def __init__(self, sales_client: FakePosSalesClient, cash_client: FakePosCashClient) -> None:
        self._sales = sales_client
        self._cash = cash_client

    def pos_sales_client(self) -> FakePosSalesClient:
        return self._sales

    def pos_cash_client(self) -> FakePosCashClient:
        return self._cash


def _sale_response(total_due: str = "100.00") -> PosSaleResponse:
    return PosSaleResponse(
        header=PosSaleHeader(id="sale-1", status="DRAFT", total_due=Decimal(total_due), paid_total=Decimal("0.00")),
        lines=[
            PosSaleLine(
                id="line-1",
                line_type="SKU",
                qty=1,
                unit_price=Decimal("100.00"),
                line_total=Decimal("100.00"),
                snapshot=PosSaleLineSnapshot(sku="SKU-1", description="Test SKU"),
            )
        ],
        payments=[PosPaymentResponse(method="CASH", amount=Decimal("0.00"))],
    )


def _gate(*allowed: str) -> PermissionGate:
    return PermissionGate([{"key": key, "allowed": True} for key in allowed])


def test_draft_sale_create_and_load_flow() -> None:
    sales_client = FakePosSalesClient(sale=_sale_response(), list_rows=[_sale_response()])
    cash_client = FakePosCashClient(session=PosCashSessionSummary(status="OPEN"))
    session = FakeSession(sales_client, cash_client)
    view = SaleEditorView(
        service=PosSalesService(session=session),  # type: ignore[arg-type]
        cash_service=PosCashService(session=session),  # type: ignore[arg-type]
        gate=_gate("pos.sales.write", "pos.sales.checkout", "pos.sales.cancel"),
        lines=[{"line_type": "SKU", "qty": 1, "unit_price": "100.00", "snapshot": {"sku": "SKU-1"}}],
    )

    create_result = view.create_draft(store_id="store-1")
    load_ok = view.load("sale-1")

    assert create_result["ok"] is True
    assert create_result["transaction_id"]
    assert create_result["idempotency_key"]
    assert load_ok is True
    assert view.sale_id == "sale-1"


def test_add_edit_remove_line_behavior() -> None:
    view = SaleEditorView(
        service=PosSalesService(session=FakeSession(FakePosSalesClient(sale=_sale_response(), list_rows=[]), FakePosCashClient(session=None))),  # type: ignore[arg-type]
        cash_service=PosCashService(session=FakeSession(FakePosSalesClient(sale=_sale_response(), list_rows=[]), FakePosCashClient(session=None))),  # type: ignore[arg-type]
        gate=_gate("pos.sales.write"),
    )

    bad = view.add_line({"line_type": "SKU", "qty": 0, "unit_price": "10.00"})
    added = view.add_line({"line_type": "SKU", "qty": 2, "unit_price": "10.00"})
    edited = view.edit_line(0, {"qty": 3})
    removed = view.remove_line(0)

    assert bad["ok"] is False
    assert added["ok"] is True
    assert added["cart"]["line_total"] == Decimal("20.00")
    assert edited["cart"]["line_total"] == Decimal("30.00")
    assert removed["cart"]["count"] == 0


def test_payment_validation_matrix_card_transfer_and_mixed_calculation() -> None:
    sales_client = FakePosSalesClient(sale=_sale_response(), list_rows=[_sale_response()])
    session = FakeSession(sales_client, FakePosCashClient(session=PosCashSessionSummary(status="OPEN")))
    view = SaleEditorView(
        service=PosSalesService(session=session),  # type: ignore[arg-type]
        cash_service=PosCashService(session=session),  # type: ignore[arg-type]
        gate=_gate("pos.sales.checkout"),
        sale_id="sale-1",
        total_due=Decimal("100.00"),
    )

    view.payments = [{"method": "CARD", "amount": "100.00"}]
    card_fail = view.checkout()

    view.payments = [{"method": "TRANSFER", "amount": "100.00", "bank_name": "BCA"}]
    transfer_fail = view.checkout()

    view.payments = [
        {"method": "CASH", "amount": "60.00"},
        {"method": "CARD", "amount": "40.00", "authorization_code": "AUTH-1"},
    ]
    summary = view.payment_summary()

    assert card_fail["ok"] is False
    assert any("authorization_code" in issue for issue in card_fail["issues"])
    assert transfer_fail["ok"] is False
    assert any("voucher_number" in issue or "bank_name" in issue for issue in transfer_fail["issues"])
    assert summary["paid_total"] == Decimal("100.00")
    assert summary["missing_amount"] == Decimal("0.00")
    assert summary["change_amount"] == Decimal("0.00")


def test_checkout_blocked_when_cash_used_without_open_session() -> None:
    sales_client = FakePosSalesClient(sale=_sale_response(), list_rows=[])
    session = FakeSession(sales_client, FakePosCashClient(session=PosCashSessionSummary(status="CLOSED")))
    view = SaleEditorView(
        service=PosSalesService(session=session),  # type: ignore[arg-type]
        cash_service=PosCashService(session=session),  # type: ignore[arg-type]
        gate=_gate("pos.sales.checkout"),
        sale_id="sale-1",
        total_due=Decimal("100.00"),
        payments=[{"method": "CASH", "amount": "100.00"}],
    )

    result = view.checkout()

    assert result["ok"] is False
    assert "OPEN cash session" in result["error"]


def test_checkout_success_path_includes_idempotency_metadata() -> None:
    sales_client = FakePosSalesClient(sale=_sale_response(), list_rows=[])
    session = FakeSession(sales_client, FakePosCashClient(session=PosCashSessionSummary(status="OPEN")))
    view = SaleEditorView(
        service=PosSalesService(session=session),  # type: ignore[arg-type]
        cash_service=PosCashService(session=session),  # type: ignore[arg-type]
        gate=_gate("pos.sales.checkout"),
        sale_id="sale-1",
        total_due=Decimal("100.00"),
        payments=[{"method": "CASH", "amount": "100.00"}],
    )

    result = view.checkout()

    assert result["ok"] is True
    assert result["transaction_id"]
    assert result["idempotency_key"]
    assert sales_client.checkout_calls and sales_client.checkout_calls[0]["action"] == "checkout"


def test_cancel_action_flow() -> None:
    sales_client = FakePosSalesClient(sale=_sale_response(), list_rows=[])
    session = FakeSession(sales_client, FakePosCashClient(session=PosCashSessionSummary(status="OPEN")))
    view = SaleEditorView(
        service=PosSalesService(session=session),  # type: ignore[arg-type]
        cash_service=PosCashService(session=session),  # type: ignore[arg-type]
        gate=_gate("pos.sales.cancel"),
        sale_id="sale-1",
    )

    no_confirm = view.cancel(confirmed=False)
    confirmed = view.cancel(confirmed=True)

    assert no_confirm["ok"] is False
    assert confirmed["ok"] is True
    assert confirmed["idempotency_key"]
    assert sales_client.cancel_calls and sales_client.cancel_calls[0]["action"] == "cancel"


def test_cash_session_actions_wiring_and_state_gating() -> None:
    session = FakeSession(FakePosSalesClient(sale=_sale_response(), list_rows=[]), FakePosCashClient(session=None))
    view = CashSessionView(service=PosCashService(session=session), gate=_gate("pos.cash.view", "pos.cash.write"))  # type: ignore[arg-type]

    view.load_current(store_id="store-1")
    open_result = view.open(
        {"store_id": "store-1", "opening_amount": "100.00", "business_date": "2026-01-05", "timezone": "UTC"}
    )
    in_result = view.cash_in({"store_id": "store-1", "amount": "30.00"})
    out_result = view.cash_out({"store_id": "store-1", "amount": "20.00"})
    close_result = view.close({"store_id": "store-1", "counted_cash": "110.00"})
    blocked_after_close = view.cash_in({"store_id": "store-1", "amount": "10.00"})

    assert open_result["ok"] is True
    assert in_result["ok"] is True
    assert out_result["ok"] is True
    assert close_result["ok"] is True
    assert blocked_after_close["ok"] is False
    assert "not allowed" in blocked_after_close["error"]


def test_permission_gating_hides_and_disables_unauthorized_actions() -> None:
    sales_session = FakeSession(FakePosSalesClient(sale=_sale_response(), list_rows=[]), FakePosCashClient(session=None))
    sales_list = SalesListView(service=PosSalesService(session=sales_session), gate=_gate("pos.sales.view"))  # type: ignore[arg-type]

    cash_session = CashSessionView(service=PosCashService(session=sales_session), gate=_gate("pos.cash.view"))  # type: ignore[arg-type]

    sales_render = sales_list.render()
    cash_render = cash_session.render()

    assert sales_render["actions"]["checkout"] is False
    assert sales_render["actions"]["cancel"] is False
    assert cash_render["can_mutate"] is False


def test_mapped_api_errors_surface_correctly_in_ui() -> None:
    denied = ApiError(
        code="PERMISSION_DENIED",
        message="Permission denied",
        details={"message": "tenant mismatch"},
        status_code=403,
        trace_id="trace-denied",
    )
    session = FakeSession(
        FakePosSalesClient(sale=_sale_response(), list_rows=[], fail_get=denied),
        FakePosCashClient(session=PosCashSessionSummary(status="OPEN"), fail_action=denied),
    )
    sale_view = SaleEditorView(
        service=PosSalesService(session=session),  # type: ignore[arg-type]
        cash_service=PosCashService(session=session),  # type: ignore[arg-type]
        gate=_gate("pos.sales.write"),
    )
    cash_view = CashSessionView(service=PosCashService(session=session), gate=_gate("pos.cash.view", "pos.cash.write"))  # type: ignore[arg-type]

    load_ok = sale_view.load("sale-1")
    cash_view.session_payload = {"status": "OPEN"}
    cash_result = cash_view.cash_in({"store_id": "store-1", "amount": "10.00"})

    assert load_ok is False
    assert sale_view.error_message == "Permission denied"
    assert sale_view.trace_id == "trace-denied"
    assert cash_result["ok"] is False
    assert cash_result["trace_id"] == "trace-denied"


def test_cash_movements_view_loads_rows() -> None:
    session = FakeSession(FakePosSalesClient(sale=_sale_response(), list_rows=[]), FakePosCashClient(session=PosCashSessionSummary(status="OPEN")))
    view = CashMovementsView(service=PosCashService(session=session), gate=_gate("pos.cash.view"))  # type: ignore[arg-type]

    ok = view.load(store_id="store-1")

    assert ok is True
    assert view.total == 1
    assert view.rows[0]["movement_type"] == "CASH_IN"
